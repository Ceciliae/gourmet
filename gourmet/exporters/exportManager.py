import gourmet.plugin_loader as plugin_loader
from gourmet.plugin import ExporterPlugin
import gourmet.gtk_extras.dialog_extras as de
from gourmet.threadManager import get_thread_manager, get_thread_manager_gui
from gourmet.prefs import get_prefs
from gourmet.gtk_extras import optionTable, DragDrop,cb_extras, treeview_extras
import gtk
from glib import get_user_special_dir, USER_DIRECTORY_DOCUMENTS
from gettext import gettext as _
import os.path

EXTRA_PREFS_AUTOMATIC = -1
EXTRA_PREFS_DEFAULT = 0

SORTED_PREFS_AUTOMATIC = -1
SORTED_PREFS_DEFAULT = 0

class ExportManager (plugin_loader.Pluggable):

    '''A class to manage exporters.
    '''

    __single = None

    def __init__ (self):
        if ExportManager.__single: raise ExportManager.__single
        else: ExportManager.__single = self
        self.plugins_by_name = {}
        plugin_loader.Pluggable.__init__(self,
                                         [ExporterPlugin]
                                         )
        from gourmet.GourmetRecipeManager import get_application
        self.app = get_application()

    def offer_single_export (self, rec, prefs, mult=1, parent=None):
        """Offer to export a single file.

        Return the filename if we have in fact exported said file.
        """
        default_extension = prefs.get('save_recipe_as','html')
        # strip the period if one ended up on our default extension
        if default_extension and default_extension[0]=='.':
            default_extension = default_extension[1:]
        exp_directory = prefs.get('rec_exp_directory',
                                  get_user_special_dir(USER_DIRECTORY_DOCUMENTS)
                                  )
        filename,exp_type = de.saveas_file(_('Save recipe as...'),
                                           filename='%s%s%s%s%s'%(exp_directory,
                                                                  os.path.sep,
                                                                  rec.title,
                                                                  os.path.extsep,
                                                                  default_extension),
                                           filters=self.get_single_filters(),
                                           parent=parent
                                           )
        if not filename: return
        if not exp_type or not self.can_export_type(exp_type):
            de.show_message(label=_('Gourmet cannot export file of type "%s"')%os.path.splitext(filename)[1])
            return
        return self.do_single_export(rec, filename, exp_type, mult)
        
    def do_single_export (self, rec, filename, exp_type, mult=1, extra_prefs=EXTRA_PREFS_AUTOMATIC):
        exporter_plugin = self.get_exporter(exp_type)
        extra_prefs = self.get_extra_prefs(exporter_plugin,extra_prefs)
        #extra_prefs = exporter_plugin.run_extra_prefs_dialog() or {}
        if hasattr(exporter_plugin,'mode'):
            export_file_mode = exporter_plugin.mode
            if export_file_mode not in ['w','a','wb']:
                print 'IGNORING INVALID FILE MODE',export_file_mode
                export_file_mode = 'w'
        else:
            export_file_mode = 'w'
        outfi = file(filename,
                     export_file_mode)
        # this should write to our file...
        exporter_plugin.do_single_export({
            'rd':self.app.rd,
            'rec':rec,
            'out':outfi,
            'conv':self.app.conv,
            'change_units':self.app.prefs.get('readableUnits',True),
            'mult':mult,     
            'extra_prefs':extra_prefs,
            })
        outfi.close()
        return filename

    def offer_multiple_export (self, recs, prefs, parent=None, prog=None,
                               export_all=False):
        """Offer user a chance to export multiple recipes at once.

        Return the exporter class capable of doing this and a
        dictionary of arguments for the progress dialog.
        """
        if (not export_all) or (len(recs) < 950):
            # inelegantly avoid bug that happens when this code runs
            # on large numbers of recipes. The good news is that this
            # that that will almost only ever happen when we're
            # exporting all recipes, which makes this code irrelevant
            # anyway.
            self.app.rd.include_linked_recipes(recs)
        ext = prefs.get('save_recipes_as','%sxml'%os.path.extsep)
        exp_directory = prefs.get('rec_exp_directory',
                                  get_user_special_dir(USER_DIRECTORY_DOCUMENTS)
                                  )
        fn,exp_type=de.saveas_file(_("Export recipes"),
                                     filename="%s%s%s%s"%(exp_directory,
                                                          os.path.sep,
                                                          _('recipes'),
                                                          ext),
                                     parent=parent,
                                     filters=self.get_multiple_filters())
        if fn:
            prefs['rec_exp_directory']=os.path.split(fn)[0]
            prefs['save_recipes_as']=os.path.splitext(fn)[1]
            instance = self.do_multiple_export(recs, fn, exp_type)
            if not instance:
                de.show_message(
                    okay=gtk.STOCK_CLOSE,
                    cancel=False,
                    label=_('Unable to export: unknown filetype "%s"'%fn),
                    sublabel=_('Please make sure to select a filetype from the dropdown menu when saving.'),
                    message_type=gtk.MESSAGE_ERROR,
                    )
                return
            return instance

    def get_extra_prefs (self, myexp, extra_prefs):
        if extra_prefs == EXTRA_PREFS_AUTOMATIC:
            extra_prefs = myexp.run_extra_prefs_dialog() or {}
        elif extra_prefs == EXTRA_PREFS_DEFAULT:
            extra_prefs = myexp.get_default_prefs()
        else:
            extra_prefs = extra_prefs
        return extra_prefs
        
    def get_sorted_prefs (self, myexp, sorted_prefs, chapter, index, args):
        if sorted_prefs == SORTED_PREFS_AUTOMATIC:
            sorterDialog = SorterDialog(chapter, index, args)
            sorted_prefs = sorterDialog.run_sorted_prefs()
        elif sorted_prefs == SORTED_PREFS_DEFAULT:
            sorted_prefs = self.get_default_sorted_prefs()
        else:
            sorted_prefs=sorted_prefs
        return sorted_prefs
    def get_multiple_exporter (self, recs, fn, exp_type=None,
                               setup_gui=True, extra_prefs=EXTRA_PREFS_AUTOMATIC, sorted_prefs=SORTED_PREFS_AUTOMATIC):
        if not exp_type:
            exp_type = de.get_type_for_filters(fn,self.get_multiple_filters())
        if self.can_export_type(exp_type):
            myexp = self.get_exporter(exp_type)
            extra_prefs = self.get_extra_prefs(myexp,extra_prefs) 
            if self.chapter_sorted or self.indices:
                extra_prefs.update(self.get_sorted_prefs(myexp, sorted_prefs, myexp.chapter_sorted, myexp.indices, {'rd':self.app.rd, 'rv':recs}))
            #pd_args={'label':myexp.label,'sublabel':myexp.sublabel%{'file':fn}}
            exporterInstance = myexp.get_multiple_exporter({'rd':self.app.rd,
                                                         'rv': recs,
                                                            #'conv':self.app.conv,
                                                            #'prog':,
                                                         'file':fn,
                                                         'extra_prefs':extra_prefs,
                                                         })        
            return myexp, exporterInstance
        else:
            print 'WARNING: CANNOT EXPORT TYPE',exp_type        

    def do_multiple_export (self, recs, fn, exp_type=None,
                                           setup_gui=True, extra_prefs=EXTRA_PREFS_AUTOMATIC):
            myexp, exporterInstance = self.get_multiple_exporter(recs,fn,exp_type,setup_gui,extra_prefs)
            tm = get_thread_manager()
            tm.add_thread(exporterInstance)
            if setup_gui:
                tmg = get_thread_manager_gui()
                tmg.register_thread_with_dialog(_('Export')+' ('+myexp.label+')',
                                                exporterInstance)
                exporterInstance.connect('completed', tmg.notification_thread_done,
                    _('Recipes successfully exported to <a href="file:///%s">%s</a>')%(fn,fn))
                tmg.show()
            print 'Return exporter instance'
            return exporterInstance        

    def can_export_type (self, name): return self.plugins_by_name.has_key(name)

    def get_exporter (self, name):
        exp=self.plugins_by_name[name]
        if hasattr(exp, 'chapter_sorted'):
            self.chapter_sorted=exp.chapter_sorted
        else:
            self.chapter_sorted=False
        if hasattr(exp, 'indices'):
            self.indices=exp.indices
        else:
            self.indices=False
        return exp

    def get_single_filters (self):
        filters = []
        for plugin in self.plugins:
            filters.append(plugin.saveas_single_filters)
        return filters

    def get_multiple_filters (self):
        filters = []
        for plugin in self.plugins:
            filters.append(plugin.saveas_filters)
        return filters

    def register_plugin (self, plugin):
        name = plugin.saveas_filters[0]
        if self.plugins_by_name.has_key(name):
            print 'WARNING','replacing',self.plugins_by_name[name],'with',plugin
        self.plugins_by_name[name] = plugin

    def unregister_plugin (self, plugin):
        name = plugin.saveas_filters[0]
        if self.plugins_by_name.has_key(name):
            del self.plugins_by_name[name]
        else:
            print 'WARNING: unregistering ',plugin,'but there seems to be no plugin for ',name
    
    def get_default_sorted_prefs(self):
        pass
        
SORTER_DIALOG_DEFAULT={'chapter_sorted_by':_('Category'),
                   'ingridiance-index': False,
                   'alphabetic-index': False,
                   _('Category'):False,
                   'preperation-time-index':False,
                   'rating-index':False,
                   'cooking-time-index':False,
                   'cuisine-index':False,
                   _('Category')+'-sort':[],
                   _('cuisine')+'-sort':[]
                   }
class SorterDialog(de.ModalDialog):
    CHAPTER={_('Category'):'category', _('alphabetic'):'alphabetic', _('cuisine'):'cuisine'}
    def __init__(self, chapter, index, args):
        modal=True
        self.apply_func = None
        self.prefs = get_prefs()
        defaults = self.prefs.get('SORTER_DIALOG',SORTER_DIALOG_DEFAULT)
        print defaults
        self.chapter_bool=chapter
        self.index_bool=index
            
        de.ModalDialog.__init__(self, okay=True, label="Select Option")
        self.hbox=gtk.HBox()
        self.hbox.show()
        self.lastchapter=None
        #selected indices
        self.index_active=dict.fromkeys([_('Category'),_('Ingridiance'),_('alphabetic'),_('rating'),_('cooking time'),_('preperation time'),_('cuisine')], False)
        #shown dragdroplists in index collumn
        self.index_shown=dict.fromkeys([_('Category'),_('cuisine')], False)
        #DragDropLists:
        if _('Category')+'-sort' in defaults:
            self.chaptercat=DragDrop.DragDropList(defaults[_('Category')+'-sort'], _('Category'))
        else:
            categories=args['rd'].fetch_count(args['rd'].categories_table,'category')
            self.chaptercat=DragDrop.DragDropList([r[1] for r in categories],_('Category'))
        self.chaptercat.set_name(_('Category'))
        
        cuisine=args['rd'].fetch_count(args['rd'].recipe_table,'cuisine')
        if _('cuisine')+'-sort' in defaults:
            self.cuisinecat=DragDrop.DragDropList(defaults[ _('cuisine')+'-sort'],  _('cuisine'))
        else:
            cuisine=args['rd'].fetch_count(args['rd'].recipe_table,'cuisine')
            self.cuisinecat=DragDrop.DragDropList([r[1] for r in cuisine], _('cuisine'))
        self.cuisinecat.set_name(_('cuisine'))
        
       # ingridiences=args['rd'].fetch_count(args['rd'].ingredients_table, 'inggroup')
       # self.ingridienceList=gtk.ListStore(ingridiences)
       # self.ingridiencecat=treeview_extras.selectionSaver(self.ingridienceList) 
       # self.ingridiencecat.set_name(_('ingridience'))
        
        self.dragdroplists={_('Category'): self.chaptercat, _('cuisine'): self.cuisinecat}
        # set vboxes
        if self.chapter_bool:
            self.optionschapter = [
            [_('Chapter_Sorted_By')+':',(defaults.get(_('chapter_sorted'),SORTER_DIALOG_DEFAULT['chapter_sorted_by']),self.CHAPTER.keys())],
            ] 
            self.tablechapter = optionTable.OptionTable(options=self.optionschapter,
                                             changedcb=self.changedcb)
            widget=self.tablechapter.get_children()[0]
            widget.connect('changed',self.chapterchanged)
            self.vboxleft=gtk.VBox()
            self.vboxleft.show()
            self.vboxleft.add(self.tablechapter)
            self.hbox.add(self.vboxleft)
            widget.emit('changed')
        if self.index_bool:
            self.optionsindex=[
            [_('Ingridiance')+':',bool(defaults.get(_('Ingridiance')+'-index',SORTER_DIALOG_DEFAULT['ingridiance-index']))],
            [_('Category')+':',bool(defaults.get(_('Category')+'-index',SORTER_DIALOG_DEFAULT[_('Category')]))],
            [_('alphabetic')+':',bool(defaults.get(_('alphabetic')+'-index',SORTER_DIALOG_DEFAULT['alphabetic-index']))],
            [_('rating')+':',bool(defaults.get(_('rating')+'-index',SORTER_DIALOG_DEFAULT['rating-index']))],
            [_('cooking time')+':',bool(defaults.get(_('cooking time')+'-index',SORTER_DIALOG_DEFAULT['cooking-time-index']))],
            [_('preperation time')+':',bool(defaults.get(_('preperation time')+'-index',SORTER_DIALOG_DEFAULT['preperation-time-index']))],
            [_('cuisine')+':',bool(defaults.get(_('cuisine')+'-index',SORTER_DIALOG_DEFAULT['cuisine-index']))],
            ]
            self.tableindex = optionTable.OptionTable(options=self.optionsindex,
                                             option_label="Indices",
                                             value_label="",
                                             changedcb=self.changedcb)
            children=self.tableindex.get_children()
            for child in children:
                print "child", type(child)
                if type(child)== gtk.CheckButton:
                    child.connect('toggled', self.indexchanged)
                    child.emit('toggled')
            self.vboxright=gtk.VBox()
            self.vboxright.show()
            self.vboxright.add(self.tableindex)
            self.hbox.add(self.vboxright)
        
        #start
        self.vbox.add(self.hbox)
        dont_ask_cb=False
        if dont_ask_cb:
            if not dont_ask_custom_text:
                dont_ask_custom_text=_("Don't ask me this again.")
            self.dont_ask = gtk.CheckButton(dont_ask_custom_text)
            self.dont_ask.connect('toggled',dont_ask_cb)
            self.vbox.add(self.dont_ask)
        self.vbox.show_all()

    def setup_buttons (self, cancel, okay):
        self.changedcb=None
        self.set_modal(False)
        de.ModalDialog.setup_buttons(self, cancel, okay)
    def run_sorted_prefs(self):
        print "self.sorted_prefs"
        self.show()
        print "self.run"
        if self.apply_func:
            print "self.apply_func", self.apply_func
            return
        else:
            gtk.main()
            print "run", self.ret
            return self.ret

    def get_prefs(self):  
        print "self.get_prefs" 
        sorted_prefs={}
        if not get_prefs().has_key('SORTER_DIALOG'):
            get_prefs()['SORTER_DIALOG'] = {}
        prefs = get_prefs()['SORTER_DIALOG']
        if self.lastchapter!=None:
            sorted_prefs['chapter_sorted']=self.lastchapter.name
            prefs['chapter_sorted']=self.lastchapter.name
            for chapter in self.dragdroplists.keys():
                if self.lastchapter.name==chapter:
                    sorted_prefs['chapter_sorted_order']=self.dragdroplists[chapter].rows
                    prefs[self.lastchapter.name+'-sort']=self.dragdroplists[chapter].rows
        indices={}
        for index in self.index_active.keys():
            prefs[index+'-index']=self.index_active[index]
            if self.index_active[index]:
                if index in self.dragdroplists.keys():
                    indices[index]=self.dragdroplists[index].rows
                    prefs[index+'-sort']=self.dragdroplists[index].rows
                else:
                    indices[index]=""
        sorted_prefs['indices']=indices
        print "sorted_prefs", sorted_prefs
        return sorted_prefs
    def chapterchanged(self,args):
        active=cb_extras.cb_get_active_text(args) 
        #remove old from chapter side
        if self.lastchapter!= None:
            #print "chapterchanged", self.lastchapter
            self.vboxleft.remove(self.lastchapter)
            chapter=self.lastchapter.name
            print "add chapter to right side", chapter, self.index_active.keys(), self.dragdroplists.keys(), self.index_active[chapter]
            if chapter in self.dragdroplists.keys() and chapter in self.index_active.keys() and self.index_active[chapter]:
                    self.vboxright.add(self.lastchapter)
                    self.index_shown[chapter]=True
        #add new to chapter side
        if active in self.dragdroplists.keys():
            if active in self.index_shown.keys() and self.index_shown[active]:
                #print "chapterchanged remove right", chapter
                self.vboxright.remove(self.dragdroplists[active])
                self.index_shown[active]=False
            self.vboxleft.add(self.dragdroplists[active])
            self.lastchapter=self.dragdroplists[active]
            self.vboxleft.show_all()
        else:
            self.lastchapter=None
    def okcb (self, *args):
        if self.apply_func:
            if self.apply.get_property('sensitive'):
                # if there are unsaved changes...
                if getBoolean(label="Would you like to apply the changes you've made?"):
                    self.applycb()
            self.hide()
        else:
           # self.table.apply()
            self.ret = self.get_prefs()
            self.hide()
            gtk.main_quit()
                   
    def cancelcb (self, *args):
        self.hide()
        self.ret=None
    def indexchanged(self,args):
        index=args.name[:-1]
        if args.get_active(): #Button choosen
            if index in self.index_shown.keys():
                if self.lastchapter!=self.dragdroplists[index]:
                    self.vboxright.add(self.dragdroplists[index])
                    self.index_shown[index]=True
        else:
            if index in self.index_shown.keys():
                if not self.lastchapter==self.dragdroplists[index]:
                    #print "indexchanged", index
                    self.vboxright.remove(self.dragdroplists[index])
                    self.index_shown[index]=False
        self.index_active[index]=args.get_active()

def get_export_manager ():
    try:
        return ExportManager()
    except ExportManager, em:
        return em
