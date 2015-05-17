import re, os.path, os, xml.sax.saxutils, time, shutil, urllib, textwrap, types
from gourmet import convert
from gourmet.gglobals import REC_ATTR_DIC, DEFAULT_ATTR_ORDER, DEFAULT_TEXT_ATTR_ORDER, TEXT_ATTR_DIC, use_threads
from gourmet.gdebug import TimeAction, debug, print_timer_info
from gettext import gettext as _
from gourmet.gtk_extras import dialog_extras as de
from gourmet.plugin_loader import Pluggable, pluggable_method
from gourmet.plugin import BaseExporterPlugin, BaseExporterMultiRecPlugin
from gourmet.threadManager import SuspendableThread

class exporter (SuspendableThread, Pluggable):
    """A base exporter class.

    All Gourmet exporters should subclass this class or one of its
    derivatives.

    This class can also be used directly for plain text export.
    """
    DEFAULT_ENCODING = 'utf-8'

    name='exporter'
    ALLOW_PLUGINS_TO_WRITE_NEW_FIELDS = True
    
    def __init__ (self, rd, r, out,
                  conv=None,
                  imgcount=1,
                  order=['image','attr','ings','text'],
                  attr_order=DEFAULT_ATTR_ORDER,
                  text_attr_order = DEFAULT_TEXT_ATTR_ORDER,
                  do_markup=True,
                  use_ml=False,
                  convert_attnames=True,
                  fractions=convert.FRACTIONS_ASCII,

                  ):
        """Instantiate our exporter.

        conv is a preexisting convert.converter() class
        imgcount is a number we use to start counting our exported images.
        order is a list of our core elements in order: 'image','attr','text' and 'ings'
        attr_order is a list of our attributes in the order we should export them:
                   title, category, cuisine, servings, source, rating, preptime, cooktime
        text_attr_order is a list of our text attributes.
        do_markup is a flag; if true, we interpret tags in text blocks by calling
                  self.handle_markup to e.g. to simple plaintext renderings of tags.
        use_ml is a flag; if true, we escape strings we output to be valid *ml
        convert_attnames is a flag; if true, we hand write_attr a translated attribute name
                         suitable for printing or display. If not, we just hand it the standard
                         attribute name (this is a good idea if a subclass needs to rely on the
                         attribute name staying consistent for processing, since converting attnames
                         will produce locale specific strings.
        """
	self.attr_order=attr_order
        self.text_attr_order = text_attr_order
        self.out = out
        self.r = r
        self.rd=rd
        self.do_markup=do_markup
        self.fractions=fractions
        self.use_ml=use_ml
        self.convert_attnames = convert_attnames
        if not conv: conv=convert.get_converter()
        self.conv=conv
        self.imgcount=imgcount
        self.images = []
        self.order = order
        Pluggable.__init__(self,[BaseExporterPlugin])
        SuspendableThread.__init__(self,self.name)

    def do_run (self):
        print "exporter", self.out
        self.write_head()
        for task in self.order:
            if task=='image':
                if self._grab_attr_(self.r,'image'):
                    self.write_image(self.r.image)
            if task=='attr':
                self._write_attrs_()

            elif task=='text':
                self._write_text_()
            elif task=='ings': self._write_ings_()
        self.write_foot()


    # Internal methods -- ideally, subclasses should have no reason to
    # override any of these methods.
    @pluggable_method
    def _write_attrs_ (self):
        self.write_attr_head()
        for a in self.attr_order:
            txt=self._grab_attr_(self.r,a)
            debug('_write_attrs_ writing %s=%s'%(a,txt),1)
            if txt and (
                (type(txt) not in [str,unicode])
                or
                txt.strip()
                ):
                if (a=='preptime' or a=='cooktime') and a.find("0 ")==0: pass
                else:
                    if self.convert_attnames:
                        self.write_attr(REC_ATTR_DIC.get(a,a),txt)
                    else:
                        self.write_attr(a,txt)
        self.write_attr_foot()

    @pluggable_method
    def _write_text_ (self):
        #print 'exporter._write_text_',self.text_attr_order,'!'
        for a in self.text_attr_order:
            # This code will never be called for Gourmet
            # proper... here for convenience of symbiotic project...
            if a=='step':
                steps = self._grab_attr_(self.r,a)
                if not steps: continue
                for s in steps:
                    if isinstance(s,dict):
                        dct = s
                        s = dct.get('text','')
                        img = dct.get('image','')
                        time = dct.get('time',0)
                        #print 'Exporter sees step AS:'
                        #print '  text:',s
                        #print '  image:',img
                        #print '  time:',time
                    else:
                        img = ''
                    if self.do_markup:
                        txt=self.handle_markup(s)
                    if not self.use_ml: txt = xml.sax.saxutils.unescape(s)
                    if self.convert_attnames:
                        out_a = TEXT_ATTR_DIC.get(a,a)
                    else:
                        out_a = a
                    # Goodness this is an ugly way to pass the
                    # time as a parameter... we use try/except to
                    # allow all gourmet exporters to ignore this
                    # attribute.
                    try: self.write_text(a,s,time=time)
                    except:
                        self.write_text(a,s)
                        print 'Failed to export time=',time
                        raise
                    if img:
                        self.write_image(img)
                continue
            # End of non-Gourmet code
            txt=self._grab_attr_(self.r,a)
            if txt and txt.strip():
                if self.do_markup:  txt=self.handle_markup(txt)
                #else: print 'exporter: do_markup=False'
                if not self.use_ml: txt = xml.sax.saxutils.unescape(txt)
                if self.convert_attnames:
                    self.write_text(TEXT_ATTR_DIC.get(a,a),txt)
                else:
                    self.write_text(a,txt)

    @pluggable_method
    def _write_ings_ (self):
        """Write all of our ingredients.
        """
        ingredients = self.rd.get_ings(self.r)
        if not ingredients:
            return
        self.write_inghead()
        for g,ings in self.rd.order_ings(ingredients):
            if g:
                self.write_grouphead(g)            
            for i in ings:
                amount,unit = self._get_amount_and_unit_(i)
                if self._grab_attr_(i,'refid'):
                    self.write_ingref(amount=amount,
                                      unit=unit,
                                      item=self._grab_attr_(i,'item'),
                                      refid=self._grab_attr_(i,'refid'),
                                      optional=self._grab_attr_(i,'optional')
                                      )
                else:
                    self.write_ing(amount=amount,
                                   unit=unit,
                                   item=self._grab_attr_(i,'item'),
                                   key=self._grab_attr_(i,'ingkey'),
                                   optional=self._grab_attr_(i,'optional')
                                   )
            if g:
                self.write_groupfoot()
        self.write_ingfoot()

    def _grab_attr_ (self, obj, attr):
        # This is a bit ugly -- we allow exporting categories as if
        # they were a single attribute even though we in fact allow
        # multiple categories.
        if attr=='category':
            return ', '.join(self.rd.get_cats(obj))
        try:
            ret = getattr(obj,attr)
        except:
            return None
        else:
            if attr in ['preptime','cooktime']:
                # this 'if' ought to be unnecessary, but is kept around
                # for db converting purposes -- e.g. so we can properly
                # export an old DB
                if ret and type(ret)!=str: 
                    ret = convert.seconds_to_timestring(ret,fractions=self.fractions)
            elif attr=='rating' and ret and type(ret)!=str:
                if ret/2==ret/2.0:
                    ret = "%s/5 %s"%(ret/2,_('stars'))
                else:
                    ret = "%s/5 %s"%(ret/2.0,_('stars'))
            elif attr=='servings' and type(ret)!=str:
                ret = convert.float_to_frac(ret,fractions=self.fractions)
            elif attr=='yields':
                ret = convert.float_to_frac(ret,fractions=self.fractions)
                yield_unit = self._grab_attr_(obj,'yield_unit')
                if yield_unit:
                    ret = '%s %s'%(ret,yield_unit) # FIXME: i18n? (fix also below in exporter_mult)
            if type(ret) in [str,unicode] and attr not in ['thumb','image']:
                try:
                    ret = ret.encode(self.DEFAULT_ENCODING)
                except:
                    print "oops:",ret,"doesn't look like unicode."
                    raise
            return ret

    def _get_amount_and_unit_ (self, ing):
        return self.rd.get_amount_and_unit(ing,fractions=self.fractions)

    # Below are the images inherited exporters should
    # subclass. Subclasses overriding methods should make these
    # pluggable so that plugins can fiddle about with things as they
    # see fit.

    def write_image (self, image):
        """Write image based on binary data for an image file (jpeg format)."""
        pass


    def write_head (self):
        """Write any necessary header material at recipe start."""
        pass

    def write_foot (self):
        """Write any necessary footer material at recipe end."""
        pass

    @pluggable_method
    def write_inghead(self):
        """Write any necessary markup before ingredients."""
        self.out.write("\n---\n%s\n---\n"%_("Ingredients"))

    @pluggable_method
    def write_ingfoot(self):
        """Write any necessary markup after ingredients."""
        pass

    @pluggable_method
    def write_attr_head (self):
        """Write any necessary markup before attributes."""
        pass

    @pluggable_method
    def write_attr_foot (self):
        """Write any necessary markup after attributes."""
        pass

    @pluggable_method
    def write_attr (self, label, text):
        """Write an attribute with label and text.

        If we've been initialized with convert_attnames=True, the
        label will already be translated to our current
        locale. Otherwise, the label will be the same as it used
        internally in our database.

        So if your method needs to do something special based on the
        attribute name, we need to set convert_attnames to False (and
        do any necessary i18n of the label name ourselves.
        """
        self.out.write("%s: %s\n"%(label, text.strip()))

    @pluggable_method
    def write_text (self, label, text):
        """Write a text chunk.

        This could include markup if we've been initialized with
        do_markup=False.  Otherwise, markup will be handled by the
        handle_markup methods (handle_italic, handle_bold,
        handle_underline).
        """
        self.out.write("\n---\n%s\n---\n"%label)
        ll=text.split("\n")
        for l in ll:
            for wrapped_line in textwrap.wrap(l):
                self.out.write("\n%s"%wrapped_line)
        self.out.write('\n\n')

    def handle_markup (self, txt):
        """Handle markup inside of txt."""
        if txt == None:
            print 'Warning, handle_markup handed None'
            return ''
        import pango
        outtxt = ""
        try:
            al,txt,sep = pango.parse_markup(txt,u'\x00')
        except:
            al,txt,sep = pango.parse_markup(xml.sax.saxutils.escape(txt),u'\x00')
        ai = al.get_iterator()
        more = True
        while more:
            fd,lang,atts=ai.get_font()
            chunk = xml.sax.saxutils.escape(txt.__getslice__(*ai.range()))
            trailing_newline = ''
            fields=fd.get_set_fields()
            if fields != 0: #if there are fields
                # Sometimes we get trailing newlines, which is ugly
                # because we end up with e.g. <b>Foo\n</b>
                #
                # So we define trailing_newline as a variable
                if chunk and chunk[-1]=='\n':
                    trailing_newline = '\n'; chunk = chunk[:-1]
                if 'style' in fields.value_nicks and fd.get_style()==pango.STYLE_ITALIC:
                    chunk=self.handle_italic(chunk)
                if 'weight' in fields.value_nicks and fd.get_weight()==pango.WEIGHT_BOLD:
                    chunk=self.handle_bold(chunk)
            for att in atts:
                if att.type==pango.ATTR_UNDERLINE and att.value==pango.UNDERLINE_SINGLE:
                    chunk=self.handle_underline(chunk)
            outtxt += chunk + trailing_newline
            more=ai.next()
        return outtxt

    def handle_italic (self,chunk):
        """Make chunk italic, or the equivalent."""
        return "*"+chunk+"*"
    
    def handle_bold (self,chunk):
        """Make chunk bold, or the equivalent."""
        return chunk.upper()
    
    def handle_underline (self,chunk):
        """Make chunk underlined, or the equivalent of"""
        return "_" + chunk + "_"

    @pluggable_method
    def write_grouphead (self, text):
        """The start of group of ingredients named TEXT"""
        self.out.write("\n%s:\n"%text.strip())

    @pluggable_method
    def write_groupfoot (self):
        """Mark the end of a group of ingredients.
        """
        pass
    
    @pluggable_method
    def write_ingref (self, amount=1, unit=None,
                      item=None, optional=False,
                      refid=None):
        """By default, we don't handle ingredients as recipes, but
        someone subclassing us may wish to do so..."""
        self.write_ing(amount=amount,
                       unit=unit, item=item,
                       key=None, optional=optional)

    @pluggable_method
    def write_ing (self, amount=1, unit=None, item=None, key=None, optional=False):
        """Write ingredient."""
        if amount:
            self.out.write("%s"%amount)
        if unit:
            self.out.write(" %s"%unit)
        if item:
            self.out.write(" %s"%item)
        if optional:
            self.out.write(" (%s)"%_("optional"))
        self.out.write("\n")

class exporter_mult (exporter):
    """A basic exporter class that can handle a multiplied recipe."""
    def __init__ (self, rd, r, out,
                  conv=None, 
                  change_units=True,
                  mult=1,
                  imgcount=1,
                  order=['image','attr','ings','text'],
                  attr_order=DEFAULT_ATTR_ORDER,
                  text_attr_order=DEFAULT_TEXT_ATTR_ORDER,
                  do_markup=True,
                  use_ml=False,
                  convert_attnames=True,
                  fractions=convert.FRACTIONS_ASCII,
                    ):
        """Initiate an exporter class capable of multiplying the recipe.

        We allow the same arguments as the base exporter class plus
        the following

        mult = number (multiply by this number)

        change_units = True|False (whether to change units to keep
        them readable when multiplying).
        """
        self.mult = mult
        self.change_units = change_units
        exporter.__init__(self, rd, r, out, conv, imgcount, order,
                          attr_order=attr_order,
                          text_attr_order=text_attr_order,
                          use_ml=use_ml, do_markup=do_markup,
                          convert_attnames=convert_attnames,
                          fractions=fractions,
                          )

    @pluggable_method
    def write_attr (self, label, text):
        #attr = NAME_TO_ATTR[label]
        self.out.write("%s: %s\n"%(label, text))

    def _grab_attr_ (self, obj, attr):
        """Grab attribute attr of obj obj.

        Possibly manipulate the attribute we get to hand out export
        something readable.
        """        
        if attr=='servings' or attr=='yields' and self.mult:
            ret = getattr(obj,attr)
            if type(ret) in [int,float]:
                fl_ret = float(ret)
            else:
                if ret is not None:
                    print 'WARNING: IGNORING serving value ',ret
                fl_ret = None
            if fl_ret:
                ret = convert.float_to_frac(fl_ret * self.mult,
                                            fractions=self.fractions)
                if attr=='yields' :
                    yield_unit = self._grab_attr_(obj,'yield_unit')
                    if yield_unit:
                        ret = '%s %s'%(ret,yield_unit) # FIXME: i18n?
                return ret
        else:
            return exporter._grab_attr_(self,obj,attr)

    def _get_amount_and_unit_ (self, ing):
        if self.mult != 1 and self.change_units:
            return self.rd.get_amount_and_unit(ing,mult=self.mult,conv=self.conv,
                                               fractions=self.fractions)
        else:
            return self.rd.get_amount_and_unit(ing,mult=self.mult,conv=self.conv,
                                               fractions=self.fractions)

    @pluggable_method
    def write_ing (self, amount=1, unit=None, item=None, key=None, optional=False):
        if amount:
            self.out.write("%s"%amount)
        if unit:
            self.out.write(" %s"%unit)
        if item:
            self.out.write(" %s"%item)
        if optional:
            self.out.write(" (%s)"%_("optional"))
        self.out.write("\n")         
class ExporterMultirec (SuspendableThread, Pluggable):

    name = 'Exporter'
    nocat=unicode(_("not categorized"))
    def __init__ (self, rd, recipes, out, one_file=True,
                  ext='txt',
                  conv=None,
                  imgcount=1,
                  progress_func=None,
                  exporter=exporter,
                  exporter_kwargs={},
                  padding=None,toc=False,output_type="one_file"):
        """Output all recipes in recipes into a document or multiple
        documents. if one_file, then everything is in one
        file. Otherwise, we treat 'out' as a directory and put
        individual recipe files within it."""
        print "ExporterMultirec"
        self.timer=TimeAction('exporterMultirec.__init__()')
        self.rd = rd
        self.recipes = recipes
        self.out = out
        self.padding=padding
        if "sorted_cat" in exporter_kwargs:
            self.sorted_cat=exporter_kwargs["sorted_cat"]
        else:
            self.sorted_cat=[]
        #self.one_file = one_file
        Pluggable.__init__(self,[BaseExporterMultiRecPlugin])
        SuspendableThread.__init__(self,self.name)
        if progress_func: print 'Argument progress_func is obsolete and will be ignored:',progress_func
        self.ext = ext
        self.exporter = exporter
        self.exporter_kwargs = exporter_kwargs
        self.fractions = self.exporter_kwargs.get('fractions',
                                                  convert.FRACTIONS_ASCII)
        self.DEFAULT_ENCODING = self.exporter.DEFAULT_ENCODING
        self.dictionary={}
        self.output_type=output_type
        self.toc=toc
        #if "output_type" in kwargs:
			#self.output_type=kwargs["output_type"]
        #else:
			#if one_file:
				#self.output_type="one_file"
			#else:
				#self.output_type="rezept_files"

    def _grab_attr_ (self, obj, attr):
        if attr=='category':
            return ', '.join(self.rd.get_cats(obj))
        try:
            ret = getattr(obj,attr)
        except:
            return None
        else:
            if attr in ['preptime','cooktime']:
                # this 'if' ought to be unnecessary, but is kept around
                # for db converting purposes -- e.g. so we can properly
                # export an old DB
                if ret and type(ret)!=str: 
                    ret = convert.seconds_to_timestring(ret,fractions=self.fractions)
            elif attr=='rating' and ret and type(ret)!=str:
                if ret/2==ret/2.0:
                    ret = "%s/5 %s"%(ret/2,_('stars'))
                else:
                    ret = "%s/5 %s"%(ret/2.0,_('stars'))
            if type(ret) in types.StringTypes and attr not in ['thumb','image']:
                try:
                    ret = ret.encode(self.DEFAULT_ENCODING)
                except:
                    print "oops:",ret,"doesn't look like unicode."
                    raise
            return ret

    def append_referenced_recipes (self):
        #recursiv machen???
        rec_list=self.recipes[:]
        while not rec_list==[]:
			r=rec_list.pop()
			reffed = self.rd.db.execute('select * from ingredients where recipe_id=? and refid is not null',r.id)
			for ref in reffed:
				rec=self.rd.get_rec(ref.refid)
				if not rec in self.recipes:
					print 'Appending recipe ',rec.title,'referenced in ',r.title
					self.recipes.append(rec)
					rec_list.append(rec)
        #for r in self.recipes[:]:
        #    reffed = self.rd.db.execute(
         #       'select * from ingredients where recipe_id=? and refid is not null',r.id
          #      )
          #  for ref in reffed:
           #     rec = self.rd.get_rec(ref.refid)
            #    if not rec in self.recipes:
             #       print 'Appending recipe ',rec.title,'referenced in ',r.title
              #      self.recipes.append(rec)
        
    @pluggable_method
    def do_run (self):
        self.rcount = 0
        self.rlen = len(self.recipes)   
       # print "do run", self.out,self.output_type, type(self.out)     
        if not self.output_type=="one_file":
            self.outdir=self.out
            print "do run", self.outdir
            if not os.path.exists(self.outdir):
                #shutil.rmtree(self.outdir)
                os.makedirs(self.outdir)
                #if not os.path.isdir(self.outdir):
                #    self.outdir=self.unique_name(self.outdir)
                #    os.makedirs(self.outdir)
            #else: os.makedirs(self.outdir)
        if self.output_type=="one_file" and (type(self.out)==str or type(self.out)==unicode):
            self.ofi=open(self.out,'wb')
            #print "make"
        else: self.ofi = self.out
        self.write_header()
        self.suspended = False
        self.terminated = False
        first = True
        filelist=[]
        self.append_referenced_recipes()
        ### make lists by categorie
        if self.output_type=="category-list" or self.output_type=="category-chapter":
			#print "start export", type(self.recipes), self.recipes
			recipes_in_cat={}
			for n,val in self.rd.fetch_count(self.rd.categories_table,'category'):
				recipes_in_cat[val]=[]
			recipes_in_cat[self.nocat]=[]
			for r in self.recipes:
				first=True
				for cat in self.rd.get_cats(r):
					recipes_in_cat[cat].append(r)
					if first:
						first=False
						self.dictionary[r.id]=cat
				if self.rd.get_cats(r)==[]:
					recipes_in_cat[self.nocat].append(r)
					self.dictionary[r.id]=self.nocat
		### for later?list_recipes_in_cat=[recipes_in_cat[x] for x in catsort]
		
        if self.output_type=="category-list" or self.output_type=="category-chapter":
			### not that fine, but working
			sorted_cat=self.sorted_cat
			if sorted_cat==[]:
				for n,val in self.rd.fetch_count(self.rd.categories_table,'category'):
					sorted_cat.append(val)
				sorted_cat.append(self.nocat)
			for val in sorted_cat: #define order of categorie?
				found=False
				for r in recipes_in_cat[val]:
					#print "r", type(r), r.id, r.title,  self.rd.get_cats(r)[0], val
					#print r.title
					if not found and self.output_type=="category-list" and self.dictionary[r.id]==val:
						self.write_text("headline",val)
						self.write_header("list")
					if not found and self.output_type=="category-chapter":
						fn=self.generate_filename(val,self.ext,add_id=True)
						#print "fn", fn, val
						filelist.append(fn)
						self.ofi=open(fn,'wb')
						self.write_header("chapter", headline=val,filename=fn)		
					found=True 
					self.check_for_sleep()
					if  self.output_type=="category-list":
						fn=None
						fn=self.generate_filename(r,self.ext,add_id=True)
						filelist.append(fn)
						self.ofi=open(fn,'wb')
					if self.padding and not first:
						self.ofi.write(self.padding)      
					if self.dictionary[r.id]==val:
						if self.output_type=="category-list":
							e=self.exporter(out=self.ofi, r=r, rd=self.rd,start_html=True, end_html=True, **self.exporter_kwargs)
							self.dictionary[r.title]=r.title
						if self.output_type=="category-chapter":
							e=self.exporter(out=self.ofi, r=r, rd=self.rd,start_html=False, end_html=False, **self.exporter_kwargs)
							self.dictionary[r.title]=val
						self.connect_subthread(e)
						e.do_run()
						if self.toc:
							self.write_toc(recipe=r)
						if self.output_type=="category-list":
							self.recipe_hook(r,fn,e,"list")
							e.write_foot()
							self.ofi.close()
						#else:
						#	self.recipe_hook(r,fn,e)
					else:
						self.recipe_hook(r,fn,self,"list")
				if self.output_type=="category-list" and found:
					self.write_footer("list")
				if self.output_type=="category-chapter" and found:
					e.end_html=True
					e.write_foot()
					if self.toc:
						self.write_toc(identifier="end")
					self.ofi.close()
			#self.write_footer("list")
			#write index
			self.write_header(identifier="tabular",text=_("index"))
        for r in self.recipes:
            self.check_for_sleep()
            msg = _("Exported %(number)s of %(total)s recipes")%{'number':self.rcount,'total':self.rlen}
            self.emit('progress',float(self.rcount)/float(self.rlen), msg)
            fn=None
            if not r.id in self.dictionary:
				print "one file"
				if not self.output_type=="one_file":
					fn=self.generate_filename(r,self.ext,add_id=True)
					self.ofi=open(fn,'wb')
				if self.padding and not first:
					self.ofi.write(self.padding)
				#print "exporter multi", type(self.ofi), self.ofi
				e=self.exporter(out=self.ofi, r=r, rd=self.rd, **self.exporter_kwargs)
				self.connect_subthread(e)
				e.do_run()
				self.recipe_hook(r,fn,e)
            else:
				self.recipe_hook(r,fn,self)
            if not self.output_type=="one_file" and self.ofi==file:
                print self.ofi
                self.ofi.close()
            self.rcount += 1
            first = False
        if (self.output_type=="category-chapter" or self.output_type=="category-list") and self.toc:
			self.write_footer("close",files=filelist)
        else:
			self.write_footer()
        if self.output_type=="one_file":
            self.ofi.close()
        self.timer.end()
        self.emit('progress',1,_("Export complete."))
        print_timer_info()

    @pluggable_method
    def write_header (self):
        pass

    @pluggable_method
    def write_footer (self):
        pass

    def generate_filename (self, rec, ext, add_id=False):
        if type(rec)==unicode or type(rec)==str:
			title=rec
			add_id=False
        else:
			title=rec.title
			if rec.id in self.dictionary:
				title2=self.dictionary[rec.id]
				if not title2==title:
					add_id=False
					title=title2
        # get rid of potentially confusing characters in the filename
        # Windows doesn't like a number of special characters, so for
        # the time being, we'll just get rid of all non alpha-numeric
        # characters
        ntitle = ""
        for c in title:
            if re.match("[A-Za-z0-9 ]",c):
                ntitle += c
        title = ntitle
        # truncate long filenames
        max_filename_length = 252
        if len(title) > (max_filename_length - 4):
            title = title[0:max_filename_length-4]
        # make sure there is a title
        if not title:
            title = _("Recipe")
        title=title.replace("/"," ")
        title=title.replace("\\"," ")
        title=title.replace(' ','_')
        # Add ID #
        if add_id and not type(rec)==unicode:
            title = title + str(rec.id)
        file_w_ext="%s%s%s"%(self.unique_name(title),os.path.extsep,ext)
        return os.path.join(self.outdir,file_w_ext)

    def recipe_hook (self, rec, filename=None, exporter=None):
        """Intended to be subclassed by functions that want a chance
        to act on each recipe, possibly knowing the name of the file
        the rec is going to. This makes it trivial, for example, to build
        an index (written to a file specified in write_header."""
        pass
    
    def unique_name (self, filename):
        if os.path.exists(filename):
            n=1
            fn,ext=os.path.splitext(filename)
            if ext: dot=os.path.extsep
            else: dot=""
            while os.path.exists("%s%s%s%s"%(fn,n,dot,ext)):
                n += 1
            return "%s%s%s%s"%(fn,n,dot,ext)
        else:
            return filename

    def check_for_sleep (self):
        if self.terminated:
            raise Exception("Exporter Terminated!")
        while self.suspended:
            if self.terminated:
                debug('Thread Terminated!',0)
                raise Exception("Exporter Terminated!")
            if use_threads:
                time.sleep(1)
            else:
                time.sleep(0.1)

    def terminate (self):
        self.terminated = True

    def suspend (self):
        self.suspended = True

    def resume (self):
        self.suspended = False
