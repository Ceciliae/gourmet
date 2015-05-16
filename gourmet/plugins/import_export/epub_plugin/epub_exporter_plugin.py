from gourmet.plugin import ExporterPlugin
import epub_exporter
from gettext import gettext as _

epub = _('epub e-book')

class EpubExporterPlugin (ExporterPlugin):
    label = _('Exporting e-book')
    sublabel = _('Exporting recipes to epub files in directory %(file)s')
    single_completed_string = _('Recipe saved as epub file %(file)s')
    filetype_desc = epub
    saveas_filters = [epub,['epub'],['*.epub']]
    saveas_single_filters =     [epub,['epub'],['*.epub','*.epub']]

    def get_multiple_exporter (self, args):
        return epub_exporter.book_exporter(
            args['rd'], 
            args['rv'],
            args['file'],
            epub_args=args['extra_prefs']
            #args['conv'],
            #progress_func=args['prog']
            )

    def do_single_export (self, args)    :
        he = epub_exporter.epub_exporter(
            args['rd'],
            args['rec'],
            args['out'],
            change_units=args['change_units'],
            mult=args['mult'],
            epub_args=args['extra_prefs']
            #conv=args['conv']
            )
        he.run()

    def run_extra_prefs_dialog (self):
        return epub_exporter.get_epub_prefs(self.rd,self.r)
