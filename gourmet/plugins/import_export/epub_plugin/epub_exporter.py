import re, os.path, os, xml.sax.saxutils, time, shutil, urllib, textwrap
from gettext import gettext as _
from gourmet import convert,gglobals
from gourmet.exporters.exporter import ExporterMultirec, exporter_mult
from gourmet.gtk_extras import dialog_extras as de
from gourmet.gtk_extras import optionTable
from gourmet.gtk_extras import cb_extras
#from gourmet.prefs import get_prefs
import gtk
import zipfile, zlib

HTML_HEADER_START = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xml:lang="de" xmlns="http://www.w3.org/1999/xhtml">
  <head>
  """
HTML_HEADER_CLOSE = """
     </head>"""

CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="content/content.opf" media-type="application/oebps-package+xml"/>
   </rootfiles>
</container>"""

OPF="""<?xml version='1.0' encoding='UTF-8'?>
<package xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="bookid">
  <metadata>
    <dc:title>gourmet recipes</dc:title>"""

NCX="""<?xml version="1.0" encoding="UTF-8"?>
<ncx version="2005-1" xmlns="http://www.daisy.org/z3986/2005/ncx/">
<head>"""

class epub_exporter (exporter_mult):
    def __init__ (self, rd, r, out, conv=None,
                  css=os.path.join(gglobals.style_dir,"epub.css"),
                  embed_css=True, start_html=True, end_html=True, imagedir="pics/", imgcount=1,
                  link_generator=None,
                  # exporter_mult args
                  mult=1,
                  change_units=True,**kwargs):
        """We export web pages. We have a number of possible options
        here. css is a css file which will be embedded if embed_css is
        true or referenced if not. start_html and end_html specify
        whether or not to write header info (so we can be called in
        the midst of another script writing a page). imgcount allows
        an outside function to keep number exported images, handing
        us the imgcount at the start of our export. link_generator
        will be handed the ID referenced by any recipes called for
        as ingredients. It should return a URL for that recipe
        or None if it can't reference the recipe based on the ID."""
        self.start_html=start_html
        self.end_html=end_html
        self.embed_css=embed_css
        self.css=css
        self.link_generator=link_generator
        if imagedir and imagedir[-1] != os.path.sep: imagedir += os.path.sep #make sure we end w/ slash
        if not imagedir: imagedir = "" #make sure it's a string
        self.imagedir_absolute = os.path.join(os.path.split(out.name)[0],imagedir)
        self.imagedir = imagedir
        exporter_mult.__init__(self, rd, r, out,
                               conv=conv,
                               imgcount=imgcount,
                               mult=mult,
                               change_units=change_units,
                               do_markup=True,
                               use_ml=True)
       

    def write_head (self):
        title = self._grab_attr_(self.r,'title')
        if not title: title = _('Recipe')
        title=xml.sax.saxutils.escape(title)
        if self.start_html:
            self.out.write(HTML_HEADER_START)
            self.out.write("<title>%s</title>\n"%title)
            if self.css:
                if self.embed_css:
                    self.out.write("<style type='text/css'><!--\n")
                    f=open(self.css,'r')
                    for l in f.readlines():
                        self.out.write(l)
                    f.close()
                    self.out.write("--></style>")
                else:
                    self.out.write("<link rel='stylesheet' href='%s' type='text/css' />\n"%self.make_relative_link(self.css))
            self.out.write(HTML_HEADER_CLOSE)
            self.out.write('<body>\n')
            self.out.write('<div class="index">\n')
        self.out.write('<div class="recipe">\n')        
    def write_inghead (self):
        self.out.write('<div class="ing"><h3>%s</h3><ul class="ing">'%_('Ingredients'))
    def write_image (self, image):
        imgout = os.path.join(self.imagedir_absolute,"%s.jpg"%self.imgcount)
        while os.path.isfile(imgout):
            self.imgcount += 1
            imgout = os.path.join(self.imagedir_absolute,"%s.jpg"%self.imgcount)
        if not os.path.isdir(self.imagedir_absolute):
            os.mkdir(self.imagedir_absolute)
        o = open(imgout,'wb')
        o.write(image)
        o.close()
        # we use urllib here because os.path may fsck up slashes for urls.
        self.out.write('<img src="%s" alt="%s" width="100"/>'%(self.make_relative_link("%s%s.jpg"%(self.imagedir,
                                                                            self.imgcount)), self.imgcount
                                                                )
                       )
        self.images.append(imgout)
    def write_text (self, label, text):
        attr = gglobals.NAME_TO_ATTR.get(label,label)
        if attr == 'instructions':
            self.out.write('<div class="%s"><h3 class="%s">%s</h3><div>%s</div></div>' % (attr,label,label,htmlify(text)))
        else:
            self.out.write('<div class="%s"><h3 class="%s">%s</h3>%s</div>' % (attr,label,label,htmlify(text)))

    def handle_italic (self, chunk): return "<em>" + chunk + "</em>"
    def handle_bold (self, chunk): return "<strong>" + chunk + "</strong>"
    def handle_underline (self, chunk): return "<u>" + chunk + "</u>"

    def write_attr_head (self):
        self.out.write("<div class='header'>")

    def write_attr (self, label, text):
        attr = gglobals.NAME_TO_ATTR.get(label,label)
        if attr=='link':
            webpage = text.strip('http://')
            webpage = webpage.split('/')[0]
            self.out.write('<a href="%s">'%text +
                           _('Original Page from %s')%webpage +
                           '</a>\n')
        elif attr == 'rating':
            rating, rest = text.split('/', 1)
            self.out.write('<p class="%s"><span class="label">%s:</span> <span>%s</span><span>/%s</span></p>\n' % (attr, label.capitalize(), rating, rest))
        else:
            itemprop = None
            if attr == 'title':
                itemprop = 'name'
            elif attr == 'category':
                itemprop = 'recipeCategory'
            elif attr == 'cuisine':
                itemprop = 'recipeCuisine'
            elif attr == 'yields':
                itemprop = 'recipeYield'
            elif attr == 'preptime':
                itemprop = 'prepTime'
            elif attr == 'cooktime':
                itemprop = 'cookTime'
            elif attr == 'instructions':
                itemprop = 'recipeInstructions'
            if itemprop:
				if itemprop=='name':
					self.out.write("<p class='%s'><span class='title'>%s:</span> <span><a id='%s'>%s</a></span></p>\n" % (attr, label.capitalize(), linkify(xml.sax.saxutils.escape(text)), htmlify(text,p=False)))
				else:
					self.out.write("<p class='%s'><span class='label'>%s:</span> <span>%s</span></p>\n" % (attr, label.capitalize(), htmlify(text,p=False)))
            else:
                self.out.write("<p class='%s'><span class='label'>%s: </span> %s</p>\n"%(attr, label.capitalize(), xml.sax.saxutils.escape(text)))
        
    def write_attr_foot (self):
        self.out.write("</div>")
    
    def write_grouphead (self, name):
        self.out.write("<li class='inggroup'>%s:<ul class='ing'>"%name)

    def write_groupfoot (self):
        self.out.write("</ul></li>")
                            
    def write_ingref (self, amount, unit, item, refid, optional):
        link=False
        if self.link_generator:
            link=self.link_generator(refid)
            if link:
                #self.out.write("<a href='")
                #self.out.write(
                linktext='<a href=\"'+ self.make_relative_link(link)+'\">'
                    #xml.sax.saxutils.escape(link).replace(" ","%20")
                    #self.make_relative_link(link)
                #    )
                #self.out.write("'>")
        self.write_ing (amount, unit, item, optional=optional, linktext=linktext)
        #if link: self.out.write("</a>")

    def write_ing (self, amount=1, unit=None,
                   item=None, key=None, optional=False, linktext=None):
        self.out.write('<li class="ing">')
        if linktext:
			self.out.write(linktext)
        for o in [amount, unit, item]:
            if o: self.out.write(xml.sax.saxutils.escape("%s "%o))
        if optional:
            self.out.write("(%s)"%_('optional'))
        if linktext:
			self.out.write('</a>')
        self.out.write("</li>\n")
    
    def write_ingfoot (self):
        self.out.write('</ul>\n</div>\n')

    def write_foot (self):
        self.out.write("</div>\n")
        if self.end_html:
            self.out.write('\n</body>\n</html>')
			

    def make_relative_link (self, filename):
        try:
            outdir = os.path.split(self.out.name)[0] + os.path.sep
            if filename.find(outdir)==0:
                filename=filename[len(outdir):]
        except:
            pass
        return linkify(filename)

class book_exporter (ExporterMultirec):
    def __init__ (self, rd, recipe_table, out, conv=None, ext='htm', copy_css=True,
                  css=os.path.join(gglobals.style_dir,'epub.css'),
                  imagedir='pics' + os.path.sep,
                  index_rows=['title','category','cuisine','rating','yields'],
                  progress_func=None,
                  change_units=False,
                  mult=1,**kwargs):
        self.ext=ext
        self.css=css
        self.toc_count=0
        self.embed_css = False
        #if os.path.isdir(out):
            #print "clear", out
            #shutil.rmtree(out)
        out=out+"-temp/content"
        if copy_css:
            styleout = os.path.join(out,'style.css')
            if not os.path.isdir(out):
                os.makedirs(out)
            to_copy = open(self.css,'r')
            to_paste = open(styleout,'w')
            to_paste.write(to_copy.read())
            to_copy.close()
            to_paste.close()
            self.css = styleout
        self.imagedir=imagedir
        self.imagedir_absolute = os.path.join(out,imagedir)
        self.index_rows=index_rows
        self.imgcount=1
        self.added_dict={}
        self.exportargs={'embed_css': False,
                          'css': self.css,
                          'imgcount': self.imgcount,
                         'imagedir':self.imagedir,
                         'link_generator': self.generate_link,
                         'change_units':change_units,
                         'mult':mult}
        self.exportargs['sorted_cat']=kwargs['epub_args']
        if conv:
            self.exportargs['conv']=conv
        ExporterMultirec.__init__(self, rd, recipe_table, out,
                                  one_file=False,
                                  ext=self.ext,
                                  progress_func=progress_func,
                                  exporter=epub_exporter,
                                  exporter_kwargs=self.exportargs, toc=True, output_type="category-chapter")

    def write_text(self,label,text):
		if label=="headline":
			h="h2"
		self.indexf.write("<%s> %s </%s>"%(h,text,h))
    def write_header (self,identifier="start",filename=None, **kwargs):
		if identifier=="start":
			self.contentn = os.path.join(self.outdir,'content.opf')
			self.content = open(self.contentn,'w')
			self.content.write(OPF)
			date=time.localtime(time.time())
			self.bookid="http://sourceforge.net/projects/gourmet-recipe-manager-"+str(date[0])+"_"+str(date[1])+"_"+str(date[2])+"h"+str(date[3])+":"+str(date[4])
			self.content.write(" <dc:identifier id=\"bookid\">"+self.bookid+"</dc:identifier>\n")
			self.content.write("<dc:language>En</dc:language>\n<dc:creator>gourmet recipes manager</dc:creator>\n  </metadata>\n <manifest>\n")
			self.tocn = os.path.join(self.outdir,'toc.ncx')
			self.toc = open(self.tocn,'w')
			self.toc.write(NCX)
			self.toc.write(" <meta name=\"dtb:uid\" content=\""+self.bookid+"\"/>\n <meta name=\"dtb:depth\" content=\"2\"/>\n<meta name=\"dtb:totalPageCount\" content=\"0\"/>\n<meta name=\"dtb:maxPageNumber\" content=\"0\"/>\n </head>\n")
			self.toc.write("<docTitle>\n<text>gourmet recipes</text>\n</docTitle>\n<docAuthor>\n<text>gourmet recipes manager</text>\n</docAuthor>\n<navMap>\n")
			self.indexfn = os.path.join(self.outdir,'index%s%s'%(os.path.extsep,self.ext))
			self.indexf = open(self.indexfn,'w')
			self.indexf.write(HTML_HEADER_START)
			self.indexf.write("<title>Recipe Index</title>")
			if self.embed_css:
				self.indexf.write("<style type='text/css'><!--\n")
				f=open(self.css,'r')
				for l in f.readlines():
					self.indexf.write(l)
				f.close()
				self.indexf.write("--></style>")
			else:
				self.indexf.write("<link rel='stylesheet' href='%s' type='text/css'/>"%self.make_relative_link(self.css))
			self.indexf.write(HTML_HEADER_CLOSE)
			self.indexf.write('<body>')
			self.indexf.write('<div class="index">')
			
			#zus. Dateien:
			self.covern= os.path.join(self.outdir,'cover%s%s'%(os.path.extsep,self.ext))
			self.cover=open(self.covern,'w')
			self.cover.write(HTML_HEADER_START)
			self.cover.write("<title>gourmet recipe book</title>")
			if self.embed_css:
				self.cover.write("<style type='text/css'><!--\n")
				f=open(self.css,'r')
				for l in f.readlines():
					self.cover.write(l)
				f.close()
				self.cover.write("--></style>")
			else:
				self.cover.write("<link rel='stylesheet' href='%s' type='text/css'/>"%self.make_relative_link(self.css))
			self.cover.write(HTML_HEADER_CLOSE)
			self.cover.write('<body>\n')
			self.cover.write('<div class="index">\n')
			self.cover.write('<div  style="text-align:center;"><h1> gourmet recipes book </h1>\n')
			self.cover.write('<img src="%s" alt="gourmet recipes manager logo"/>\n</div>\n'%self.make_relative_link("%sgourmet.png"%(self.imagedir)))
			self.cover.write('</div>\n</body>\n</html>')
			self.cover.close()
			script_dir = os.path.dirname(__file__)
			os.mkdir(self.imagedir_absolute)
			shutil.copy2(os.path.join(script_dir,'gourmet.png'), os.path.join(self.imagedir_absolute,'gourmet.png'))
			outdir=self.outdir[:-8]
			self.mimetypen = os.path.join(outdir, 'mimetype')
			self.mimetype = open(self.mimetypen,'w')
			self.mimetype.write("application/epub+zip")
			self.mimetype.close()
			newpath=os.path.join(outdir,'META-INF')
			os.makedirs(newpath)
			self.containern = os.path.join(outdir,'META-INF/container.xml')
			self.container=open(self.containern,'w')
			self.container.write(CONTAINER)
			self.container.close()
		if identifier=="tabular":
			if "text" in kwargs:
				text=kwargs["text"]
			self.indexf.write("<h1> %s </h1>"%(text))
			self.indexf.write('<table class="index">\n<tr>')
			for r in self.index_rows:
				self.indexf.write('<th class="%s">%s</th>'%(r,gglobals.REC_ATTR_DIC[r]))
			self.indexf.write('</tr>\n')    
		if identifier=="list":
			self.indexf.write('<ul>')
		if identifier=="chapter":
			if "headline" in kwargs:
				headline=kwargs["headline"]
			self.ofi.write(HTML_HEADER_START)
			self.ofi.write("<title>%s </title>"%headline)
			self.ofi.write("<link rel='stylesheet' href='style.css' type='text/css'/>")
			self.ofi.write(HTML_HEADER_CLOSE)
			self.ofi.write('<body>')
			self.ofi.write('<div class="index">')
			self.ofi.write('<h1>%s</h1>'%headline)
			reltext=self.make_relative_link(filename)
			self.toc.write('<navPoint id=\"'+reltext[:-4]+'_toc\" playOrder=\"'+str(self.toc_count)+'\">\n<navLabel>\n<text>'+headline+'</text>\n</navLabel>\n<content src=\"'+reltext+'\"/>\n')
			self.toc_count=self.toc_count+1
    def write_toc(self,recipe=None, identifier="recipe"):
		if identifier=="recipe":
			reltext=self.make_relative_link(self.generate_link(recipe.id))
			self.toc.write('<navPoint id=\"'+reltext[:-4]+linkify(recipe.title)+'_toc\" playOrder=\"'+str(self.toc_count)+'\">\n<navLabel>\n<text>'+recipe.title+'</text>\n</navLabel>\n<content src=\"'+reltext+'#'+linkify(recipe.title)+'\"/>\n</navPoint>\n')
			self.toc_count=self.toc_count+1	
		if identifier=="end":
			self.toc.write('</navPoint>\n')
			
			

    def recipe_hook (self, rec, filename, exporter, identifier="tabular"):
		"""Add index entry"""
		# we link from the first row
		if identifier=="tabular":
			self.indexf.write(
				"""<tr><td class="%s">
                     <a href="%s#%s">%s</a>
                   </td>"""%(self.index_rows[0],
                             #xml.sax.saxutils.escape(filename).replace(" ","%20"),
                             #self.make_relative_link(filename),
                             self.make_relative_link(self.generate_link(rec.id)), linkify(rec.title),
                             xml.sax.saxutils.escape(self._grab_attr_(rec,self.index_rows[0]))
                             ))
			for r in self.index_rows[1:]:
				self.indexf.write('<td class="%s">%s</td>'%(r,self._grab_attr_(rec,r)))
			self.indexf.write('</tr>')
			self.imgcount=exporter.imgcount
			self.added_dict[rec.id]=filename
		#else:
		#	if identifier=="list":
		#		#self.indexf.write(
		#		"""<li><a href="%s#%s">%s</a></li>"""%(
         #                    #xml.sax.saxutils.escape(filename).replace(" ","%20"),
          #                   #self.make_relative_link(filename),
           #                  self.make_relative_link(self.generate_link(rec.id)), linkify(rec.title),
           #                  xml.sax.saxutils.escape(self._grab_attr_(rec,self.index_rows[0]))
           #                  ))
				#self.indexf.write('<li>)

    def write_footer (self,identifier="tabular",**kwargs):
		if identifier=="tabular":
			self.indexf.write('</table></div></body></html>')
		if identifier=="list":
			self.indexf.write('</ul>')
		if identifier=="close":
			self.toc.write('<navPoint id=\"index_toc\" playOrder=\"'+str(self.toc_count)+'\">\n<navLabel>\n<text> index </text>\n</navLabel>\n<content src=\"index.htm\"/>\n</navPoint>\n')
			self.toc.write('</navMap>\n</ncx>')
			if "files" in kwargs:
				filelist=kwargs["files"]
				filelist.append(self.indexfn)
				#make content
				for text in filelist:
					reltext=self.make_relative_link(text)
					self.content.write("<item id=\""+reltext[:-4]+"\" href=\""+reltext+"\" media-type=\"application/xhtml+xml\" />\n")
				self.content.write("<item id=\"toc\" href=\"toc.ncx\" media-type=\"application/x-dtbncx+xml\" />\n")
				self.content.write("<item id=\"css\" href=\"style.css\" media-type=\"text/css\" />\n")
				self.content.write("<item id=\"cover\" href=\"cover.htm\" media-type=\"application/xhtml+xml\"/>\n")
				for root, dirs, files in os.walk(os.path.join(self.outdir,'pics')):
					for name in files:
						self.content.write("<item href=\"pics/"+name+"\" id=\"image-"+name+"\" media-type=\"image/"+make_image_ending(os.path.splitext(name)[1][1:])+"\"/>\n")
				self.content.write("</manifest>\n <spine toc=\"toc\"> \n <itemref idref=\"cover\"/>\n")
				for text in filelist:
					reltext=self.make_relative_link(text)
					self.content.write("<itemref idref=\""+reltext[:-4]+"\" />\n")
				self.content.write("</spine>\n</package>")
			self.indexf.write('</table>\n </div>\n  </body>\n</html>')
			self.indexf.close()
			self.content.close()
			self.toc.close()
			zfn=self.outdir[:-13]
			zf=zipfile.ZipFile(zfn, mode='w')
			zf.write(self.mimetypen,compress_type=zipfile.ZIP_STORED,arcname='mimetype')
			###to make order in zip file??
			#zf.close()
			#zf=zipfile.ZipFile(zfn, mode='a')
			zf.write(self.outdir,compress_type=zipfile.ZIP_DEFLATED,arcname='content')
			self.zipdir(self.outdir,zf,zipfile.ZIP_DEFLATED,arcname='content')
			META=os.path.join(self.outdir[:-8],'META-INF')
			zf.write(META,compress_type=zipfile.ZIP_DEFLATED,arcname='META-INF')
			self.zipdir(META,zf,zipfile.ZIP_DEFLATED,arcname='META-INF')
			zf.close()
			shutil.rmtree(self.outdir[:-8])
    def zipdir(self,path, zip,compress_type,arcname):
		storedir=[]
		for root, dirs, files in os.walk(path):
			for file in files:
				if len(dirs)<len(storedir):
					zip.write(os.path.join(root, file),compress_type=compress_type,arcname=arcname+'/'+storedir[0]+'/'+file)
				else:
					zip.write(os.path.join(root, file),compress_type=compress_type,arcname=arcname+'/'+file)
			storedir=dirs
    def generate_link (self, id):
        if self.added_dict.has_key(id):
            return self.added_dict[id]
        else:
            rec = self.rd.get_rec(id)
            if rec:
                return self.generate_filename(rec,self.ext,add_id=True)
            else:
                return None

    def make_relative_link (self, filename):
		if self.outdir[-1] != os.path.sep:
			outdir = self.outdir + os.path.sep
		else: outdir = self.outdir
		if filename.find(outdir)==0:
			filename=filename[len(outdir):]
		return linkify(filename)

def linkify (filename):
    filename = filename.replace('\\','/')
    filename = filename.replace(' ','_')
    ntitle=""
    for c in filename:
       if re.match("[A-Za-z0-9._/ ]",c):
          ntitle += c
    return xml.sax.saxutils.escape(ntitle)
    
def htmlify(text,p=True):
   t=text.strip()
   #t=xml.sax.saxutils.escape(t)
   if p:
	   t="<p>%s</p>"%t
   t=re.sub('\n\n+','</p><p>',t)
   t=re.sub('\n','<br />',t)
   t=re.sub('','"',t)
   t=re.sub('','"',t)
   t.encode('ascii', 'xmlcharrefreplace')
   return t
def make_image_ending(text):
	if text=="jpg":
		return "jpeg"
	else:
		return text
def get_epub_prefs(rd,r,defaults=None):
	if defaults: print 'WARNING: ignoring provided defaults and using prefs system instead'
	epub_pref_getter = EpubPrefGetter(rd,r)
	return epub_pref_getter.run()

class EpubPrefGetter():
	
	def __init__(self,rd,r):
		#self.opts=[['test',("1",["0","1","2"])]]
		self.opts=[]
		self.r=r
		self.rd=rd
		self.setup_widgets()
	def run(self):
		self.pd.run()
		return self.cat.get_data()
	def setup_widgets (self):
		self.pd = de.PreferencesDialog(self.opts,option_label=None,value_label=None,label=_('epub Options'))
		self.cat = cat_sorter(self.rd,self.r)
		self.pd.hbox.pack_start(self.cat.scrolledwindow,fill=True,expand=True)
		self.pd.hbox.show_all()
class cat_sorter():
	
	
	TARGETS = [
		('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),
		('text/plain', 0, 1),
		('TEXT', 0, 2),
		('STRING', 0, 3),
		]
		
	def __init__ (self,rd, r):
		self.scrolledwindow = gtk.ScrolledWindow()
		# create a liststore with one string column to use as the model
		self.liststore = gtk.ListStore(str)
		# create the TreeView using liststore
		self.treeview = gtk.TreeView(self.liststore)
		
		self.scrolledwindow.add(self.treeview)
		
		self.cell = gtk.CellRendererText()
		self.tvcolumn = gtk.TreeViewColumn('Categorie', self.cell, text=0)
		self.treeview.append_column(self.tvcolumn)
		self.treeview.set_search_column(0)
		model = self.treeview.get_model()
		# make treeview searchable
		self.treeview.set_search_column(0)
		# Allow sorting on the column
		self.tvcolumn.set_sort_column_id(0)
		# Allow enable drag and drop of rows including row move
		self.treeview.enable_model_drag_source( gtk.gdk.BUTTON1_MASK,self.TARGETS,gtk.gdk.ACTION_DEFAULT|gtk.gdk.ACTION_MOVE)
		self.treeview.enable_model_drag_dest(self.TARGETS, gtk.gdk.ACTION_DEFAULT)
		self.treeview.connect("drag_data_get", self.drag_data_get_data)
		self.treeview.connect("drag_data_received", self.drag_data_received_data)
		self.cat_list=[[_("not categorized")]]
		model.append([_("not categorized")])
		for rec in r:
			cat=rd.get_cats(rec)
			if cat != [] and cat not in self.cat_list:
				print "cat",cat, cat
				self.cat_list.append(cat)
				model.append(cat)
		print self.cat_list

	def set_page (self, *args, **kwargs):
		self.last_kwargs = kwargs
		size,areas = self.sizer.get_pagesize_and_frames_for_widget(*args,**kwargs)
		self.set_page_area(size[0],size[1],areas)
		
	def drag_data_get_data(self, treeview, context, selection, target_id,etime):
		treeselection = treeview.get_selection()
		model, iter = treeselection.get_selected()
		data = model.get_value(iter, 0)
		selection.set(selection.target, 8, data)

	def drag_data_received_data(self, treeview, context, x, y, selection,info, etime):
		model = treeview.get_model()
		data = selection.data
		print "data", data, type(data),[unicode(data)]
		drop_info = treeview.get_dest_row_at_pos(x, y)
		if [unicode(data)] in self.cat_list:
			self.cat_list.remove([unicode(data)])
			if drop_info:
				path, position = drop_info
				iter = model.get_iter(path)
				i=int(model.get_string_from_iter(iter))
				if (position == gtk.TREE_VIEW_DROP_BEFORE
					or position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
					model.insert_before(iter, [data])
					self.cat_list.insert(i,[unicode(data)])
				else:
					model.insert_after(iter, [data])
					self.cat_list.insert(i+1,[unicode(data)])
			else:
				model.append([data])
				self.cat_list.append([unicode(data)])
			if context.action == gtk.gdk.ACTION_MOVE:
				context.finish(True, True, etime)
			print self.cat_list
		return
	def get_data(self):
		liste=[]
		for i in self.cat_list:
			liste.append(i[0])
		return liste
