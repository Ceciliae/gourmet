from gourmet.gdebug import debug
import gtk, gobject
from gourmet.gtk_extras.treeview_extras import QuickTree


class DragDropList(QuickTree):
    def __init__(self, liste, name):
        targets = [
        ('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),
        ('text/plain', 0, 1),
        ('TEXT', 0, 2),
        ('STRING', 0, 3),
        ]
        QuickTree.__init__(self, liste, name)
        #Allow sorting on the column
        self.tv.get_column(0).set_sort_column_id(0)
        self.tv.drag_source_set(gtk.gdk.BUTTON1_MASK, targets,
                             gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        self.tv.enable_model_drag_dest(targets,
                                    gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        self.tv.connect('drag_data_get', self.drag_data_get)
        self.tv.connect('drag_data_received', self.drag_data_received)
    def drag_data_get(self, tv, context, selection, target_id,etime):
        treeselection = tv.get_selection()
        model, iter = treeselection.get_selected()
        data = model.get_value(iter, 0)
        model.remove(iter)
        selection.set(selection.target, 8, data)
    def drag_data_received(self, treeview, context, x, y, selection,info, etime):
        model = treeview.get_model()
        data = selection.data
        drop_info = treeview.get_dest_row_at_pos(x, y)
        print "data", data, self.rows
        if [unicode(data)] in self.rows:
            self.rows.remove([unicode(data)])
            if drop_info:
                path, position = drop_info
                iter = model.get_iter(path)
                i=int(model.get_string_from_iter(iter))
                if (position == gtk.TREE_VIEW_DROP_BEFORE
                    or position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                    model.insert_before(iter, [data])
                    self.rows.insert(i,[unicode(data)])
                else:
                    model.insert_after(iter, [data])
                    self.rows.insert(i+1,[unicode(data)])
            else:
                model.append([data])
                self.rows.append([unicode(data)])
            if context.action == gtk.gdk.ACTION_MOVE:
                context.finish(True, True, etime)
        return
