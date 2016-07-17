import os, re
import gtk#, gobject
import xml.sax.saxutils
from gettext import gettext as _
from gourmet import convert,gglobals
from gourmet.exporters.exporter import ExporterMultirec, exporter_mult
from gourmet.prefs import get_prefs

from gourmet.gtk_extras import dialog_extras as de
from gourmet.gtk_extras import treeview_extras as te


from ebooklib import epub
from string import Template

RECIPE_HEADER = Template('''<?xml version="1.0" encoding="utf-8" standalone="no"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>$title</title>
</head>
<body>
''')
RECIPE_FOOT= "</body></html>"

EPUB_DEFAULT_CSS="epubdefault.css"


class EpubWriter():
    """This class contains all things to write an epub and is a small wrapper
    around the EbookLib which is capable of producing epub files and maybe 
    kindle in the future (it is under heavy development).
    """
    def __init__(self, outFileName):
        """
        @param outFileName The filename + path the ebook is written to on finish.
        """
        self.outFileName = outFileName
        self.lang = "en"
        self.recipeCss = None
        
        self.imgCount = 0
        self.recipeCount = 0
        
        self.ebook = epub.EpubBook()
        self.spine = ['nav']
        self.toc = []
        
        # set metadata
        self.ebook.set_identifier("Cookme") # TODO: Something meaningful or time?
        self.ebook.set_title("My Cookbook")
        self.ebook.set_language(self.lang)
        
        # This is normally the publisher, makes less sense for the moment
        # ebook.add_metadata('DC', 'publisher', "Gourmet")
            
        # TODO: Add real author from somewhere
        self.ebook.add_author("Gourmet")
               
        # This adds the field also known as keywords in some programs. 
        self.ebook.add_metadata('DC', 'subject', "cooking")
        
    def addRecipeCssFromFile(self, filename):
        """ Adds the CSS file from filename to the book. The style will be added
        to the books root.
        @param filename The file the css is read from and attached
        @return The internal name within the ebook to reference this file.
        """
        cssFileName = "Style/recipe.css"

        style = open(filename, 'rb').read()
        recipe_css = epub.EpubItem(  uid="style"
                                , file_name=cssFileName
                                , media_type="text/css"
                                , content=style)
        self.ebook.add_item(recipe_css)
        self.recipeCss = recipe_css
        return cssFileName;
        
    def addJpegImage(self, imageData):
        """Adds a jpeg image from the imageData array to the book and returns
        the reference name for the image to be used in html.
        @param imageData Image data in format jpeg
        @return The name of the image to be used in html
        """
        epimg = epub.EpubImage()
        epimg.file_name = "grf/image_%i.jpg" % self.imgCount
        self.imgCount += 1
        epimg.media_type = "image/jpeg"
        epimg.set_content(imageData)
        self.ebook.add_item(epimg)
        return epimg.file_name;
    
    def getFileForRecipeID(self, id, ext=".xhtml"):
        """
        Returns a filename to reference a specific recipe
        @param id The id which is also passed during addRecipeText
        @return A filename for reference
        """
        return "recipe_%i%s" % (id,ext)
    
    def addRecipeText(self, uniqueId, title, text):
        """ Adds the recipe text as a chapter.
        """
        uniqueName = self.getFileForRecipeID(uniqueId, ext="")
        fileName = self.getFileForRecipeID(uniqueId)
        self.recipeCount += 1
        
        c1 = epub.EpubHtml(title=title, file_name=fileName, lang=self.lang)
        c1.content = text.encode('utf-8')
        c1.add_item( self.recipeCss )
                
        # add chapter
        self.ebook.add_item(c1)
        self.spine.append(c1)
                
        # define Table Of Contents
        self.toc.append( epub.Link(fileName, title, uniqueName) )
                
    def finish(self):
        """ Finish the book and writes it to the disk.
        """
        self.ebook.toc = self.toc
    
        # add default NCX and Nav file
        self.ebook.add_item(epub.EpubNcx())
        self.ebook.add_item(epub.EpubNav())        
        
        self.ebook.spine = self.spine
        
        epub.write_epub(self.outFileName, self.ebook, {})

class epub_exporter (exporter_mult):
    def __init__ (self, rd, r, out, conv=None,
                  doc=None,
                  # exporter_mult args
                  mult=1,
                  change_units=True,
                  ):
        self.doc = doc
      
        # This document will be appended by the strings to join them in the
        # last step and pass it to the ebookwriter.
        self.preparedDocument = []
        
        #self.link_generator=link_generator
        exporter_mult.__init__(self, rd, r, out,
                               conv=conv,
                               imgcount=1,
                               mult=mult,
                               change_units=change_units,
                               do_markup=True,
                               use_ml=True)

    def htmlify (self, text):
        t=text.strip()
        #t=xml.sax.saxutils.escape(t)
        t="<p>%s</p>"%t
        t=re.sub('\n\n+','</p><p>',t)
        t=re.sub('\n','<br>',t)
        return t
    
    def get_title(self):
        """Returns the title of the book in an unescaped format"""
        title = self._grab_attr_(self.r,'title')
        if not title: title = _('Recipe')
        return unicode(title)

    def write_head (self):
        self.preparedDocument.append(
            RECIPE_HEADER.substitute(title=self.get_title()) )
        self.preparedDocument.append("<h1>%s</h1>"
             % xml.sax.saxutils.escape(self.get_title()))
        
    def write_image (self, image):
        imagePath = self.doc.addJpegImage( image)
        self.preparedDocument.append('<img src="%s" itemprop="image"/>' % imagePath)
        
    def write_inghead (self):
        self.preparedDocument.append('<div class="ing"><h2>%s</h2><ul class="ing">'%_('Ingredients'))

    def write_text (self, label, text):
        attr = gglobals.NAME_TO_ATTR.get(label,label)
        if attr == 'instructions':
            self.preparedDocument.append('<div class="%s"><h2 class="%s">%s</h2><div itemprop="recipeInstructions">%s</div></div>' % (attr,label,label,self.htmlify(text)))
        else:
            self.preparedDocument.append('<div class="%s"><h2 class="%s">%s</h2>%s</div>' % (attr,label,label,self.htmlify(text)))

    def handle_italic (self, chunk): return "<em>" + chunk + "</em>"
    def handle_bold (self, chunk): return "<strong>" + chunk + "</strong>"
    def handle_underline (self, chunk): return "<u>" + chunk + "</u>"

    def write_attr_head (self):
        self.preparedDocument.append("<div class='header'>")

    def write_attr (self, label, text):
        attr = gglobals.NAME_TO_ATTR.get(label,label)
        if attr=='link':
            webpage = text.strip('http://')
            webpage = webpage.split('/')[0]
            self.preparedDocument.append('<a href="%s">'%text +
                           _('Original Page from %s')%webpage +
                           '</a>\n')
        elif attr == 'rating':
            rating, rest = text.split('/', 1)
            self.preparedDocument.append('<p class="%s" itemprop="aggregateRating" itemscope itemtype="http://schema.org/AggregateRating"><span class="label">%s:</span> <span itemprop="ratingValue">%s</span><span>/%s</span></p>\n' % (attr, label.capitalize(), rating, rest))
        else:
            itemprop = None
            if attr == 'title':
                itemprop = 'name'
                return # Title is already printed
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
                self.preparedDocument.append('<p class="%s"><span class="label">%s:</span> <span itemprop="%s">%s</span></p>\n' % (attr, label.capitalize(), itemprop, xml.sax.saxutils.escape(text)))
            else:
                self.preparedDocument.append("<p class='%s'><span class='label'>%s:</span> %s</p>\n"%(attr, label.capitalize(), xml.sax.saxutils.escape(text)))
        
    def write_attr_foot (self):
        self.preparedDocument.append("</div>")
    
    def write_grouphead (self, name):
        self.preparedDocument.append("<h3 class='inggroup'>%s<h3/>"%name)

    def write_groupfoot (self):
        pass
    
    def _write_ing_impl(self, amount, unit, item, link, optional):
        self.preparedDocument.append('<li class="ing" itemprop="ingredients">')
        
        # Escape all incoming things first. 
        (amount, unit, item) = tuple([xml.sax.saxutils.escape("%s"%o) if o else "" for o in [amount, unit, item]])
        
        self.preparedDocument.append('<div class="ingamount">%s</div>' % (amount if len(amount) != 0 else "&nbsp;"))
        self.preparedDocument.append('<div class="ingunit">%s</div>' % (unit if len(unit) != 0 else "&nbsp;"))
        
        if item:
            if link: 
                self.preparedDocument.append( "<a href='%s'>%s</a>"% (link, item ))
            else:
                self.preparedDocument.append(item)
            
        if optional:
            self.preparedDocument.append("(%s)"%_('optional'))
        self.preparedDocument.append("</li>\n")
        
    def write_ingref (self, amount, unit, item, refid, optional):
        refFile = self.doc.getFileForRecipeID(refid)
        self._write_ing_impl(amount, unit, item, refFile, optional)

    def write_ing (self, amount=1, unit=None,
                   item=None, key=None, optional=False):
        self._write_ing_impl(amount, unit, item, None, optional)
    
    def write_ingfoot (self):
        self.preparedDocument.append('</ul>\n</div>\n')

    def write_foot (self):
        self.preparedDocument.append(RECIPE_FOOT)
        
        self._grab_attr_(self.r,'id')
        self.doc.addRecipeText(self._grab_attr_(self.r,'id'), self.get_title(), "".join(self.preparedDocument) )

class website_exporter (ExporterMultirec):
    def __init__ (self, rd, recipe_table, out, extra_prefs, conv=None, ext='epub', copy_css=True,
                  css=os.path.join(gglobals.style_dir,EPUB_DEFAULT_CSS),
                  index_rows=['title','category','cuisine','rating','yields'],
                  change_units=False,
                  mult=1):

        self.doc = EpubWriter(out)
        self.doc.addRecipeCssFromFile(css)
        
        self.ext=ext
      
        self.index_rows=index_rows
        self.exportargs={ 'change_units':change_units,
                         'mult':mult,
                         'doc':self.doc}
        
        if conv:
            self.exportargs['conv']=conv
        ExporterMultirec.__init__(self, rd, recipe_table, out,
                                  one_file=True, 
                                  open_files=False,
                                  ext=self.ext,
                                  exporter=epub_exporter,
                                  exporter_kwargs=self.exportargs)
        
    def recipe_hook (self, rec, filename, exporter):
        """Add index entry"""
        # TODO: Do some cool things here.
        pass

    def write_footer (self):
        self.doc.finish()
  
def get_epub_prefs(self,args,defaults=None):
    if defaults: print 'WARNING: ignoring provided defaults and using prefs system instead'
    print type(args['rd'].fetch_count(args['rd'].categories_table,'category'))
    epub_pref_getter = EpubPrefGetter( args['rd'].fetch_count(args['rd'].categories_table,'category'))
    return epub_pref_getter.run()

EPUB_PREF_DEFAULT={'chapter_sorted_by':_('Category'),
                   'ingridiance-index': False,
                   'alphabetic-index': False,
                   'category-index':False
                   }


class EpubPrefGetter:
    CHAPTER={_('Category'):'category', _('alphabetic'):'alphabetic'}
    def __init__(self, cats):
        
        targets = [
        ('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),
        ('text/plain', 0, 1),
        ('TEXT', 0, 2),
        ('STRING', 0, 3),
        ]
        self.prefs = get_prefs()
        defaults = self.prefs.get('EPUB_EXP',EPUB_PREF_DEFAULT)
       # self.size_strings = self.CHAPTER.keys()
       # self.size_strings.sort()
        self.opts = [
        [_('Chapter_Sorted_By')+':',(defaults.get(_('Chapter_Sorted_By'),EPUB_PREF_DEFAULT['chapter_sorted_by']),self.CHAPTER.keys())],
        [_('ingridiance index')+':',bool(defaults.get('ingridiance-index',EPUB_PREF_DEFAULT['ingridiance-index']))],
        [_('category index')+':',bool(defaults.get('category index',EPUB_PREF_DEFAULT['category-index']))],
        [_('alphabetic index')+':',bool(defaults.get('alphabetic index',EPUB_PREF_DEFAULT['alphabetic-index']))]
        ]
        if defaults.has_key("sorted_cats"):
            self.quicktree=te.QuickTree(defaults["sorted_cats"],_('Category'))
        else:
            self.quicktree=te.QuickTree([r[1] for r in cats],_('Category'))
        # Allow sorting on the column
        self.quicktree.tv.get_column(0).set_sort_column_id(0)
        self.quicktree.tv.drag_source_set(gtk.gdk.BUTTON1_MASK, targets,
                             gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        self.quicktree.tv.enable_model_drag_dest(targets,
                                    gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        self.quicktree.tv.connect('drag_data_get', self.drag_data_get)
        self.quicktree.tv.connect('drag_drop', self.on_drag_drop)
        self.quicktree.tv.connect('drag_data_received', self.drag_data_received)
        self.setup_widgets()
       # self.list_store()
       # self.add_cats([r[1] for r in cats])
    def on_drag_drop(self, tv, context, x, y, time):
        print "on_drag_drop"
        return False
    def drag_data_get(self, tv, context, selection, target_id,etime):
        print "drag_data_get"
        treeselection = tv.get_selection()
        model, iter = treeselection.get_selected()
        data = model.get_value(iter, 0)
        model.remove(iter)
        selection.set(selection.target, 8, data)
    def drag_data_received(self, treeview, context, x, y, selection,info, etime):
        print "drag_data_received"
        model = treeview.get_model()
        data = selection.data
        drop_info = treeview.get_dest_row_at_pos(x, y)
        print drop_info, context.action
        if [unicode(data)] in self.quicktree.rows:
            self.quicktree.rows.remove([unicode(data)])
            print "self.quicktree.rows", self.quicktree.rows
            if drop_info:
                path, position = drop_info
                iter = model.get_iter(path)
                i=int(model.get_string_from_iter(iter))
                if (position == gtk.TREE_VIEW_DROP_BEFORE
                    or position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                    model.insert_before(iter, [data])
                    self.quicktree.rows.insert(i,[unicode(data)])
                else:
                    model.insert_after(iter, [data])
                    self.quicktree.rows.insert(i+1,[unicode(data)])
            else:
                model.append([data])
                self.quicktree.rows.append([unicode(data)])
            if context.action == gtk.gdk.ACTION_MOVE:
                context.finish(True, True, etime)
            print self.quicktree.rows
        return
    def get_args_from_opts (self, opts):
        liste=[]
        for i in self.quicktree.rows:
            liste.append(i[0])
        extra_prefs={"sorted_cats":liste}
        if not get_prefs().has_key('EPUB_EXP'):
            get_prefs()['EPUB_EXP'] = {}
        prefs = get_prefs()['EPUB_EXP']
        prefs["sorted_cats"]=liste
        for i in opts:
            extra_prefs[i[0][:-1]]=i[1]
            prefs[i[0][:-1]]=i[1]
        return extra_prefs
    def run(self):
        self.pd.run()
        return self.get_args_from_opts(self.opts)
        
    #def list_store(self):
        #self.scrolledwindow = gtk.ScrolledWindow()
        #self.store = gtk.ListStore(str)
        #self.treeview = gtk.TreeView(self.store)
        #self.cell = gtk.CellRendererText()
        #self.tvcolumn = gtk.TreeViewColumn(_('category'), self.cell, text=0)
        #self.treeview.append_column(self.tvcolumn)
        #self.scrolledwindow.add(self.treeview)


    #def add_cats(self, cats):
        #renderer = gtk.CellRendererText()
        #column = gtk.TreeViewColumn("Title", renderer, text=0)
        #self.treeview.append_column(column)
        #treeit={}
        #for cat in cats:
            #treeit[cat]=self.store.append([cat])
        #print treeit

        
    def setup_widgets (self):
        self.pd = de.PreferencesDialog(self.opts,option_label=None,value_label=None,
                                  label=_('epub Options'),
                                  )
                                  
        #self.scrolledwindow = gtk.ScrolledWindow()
        self.quicktree.set_usize(150,100) #make it depend on size of names??
        self.pd.hbox.set_child_packing(self.pd.table, False, False, 0, gtk.PACK_START)
        self.pd.hbox.pack_end(self.quicktree, expand=True, fill=True, padding=0)
        print self.pd.vbox.get_homogeneous()
        #self.pd.vbox.add(self.quicktree)
        

        self.table = self.pd.table
        
