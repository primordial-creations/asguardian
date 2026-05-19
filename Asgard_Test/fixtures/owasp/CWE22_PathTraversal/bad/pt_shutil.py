# Path traversal via shutil.copy
import shutil
def backup(request):
    shutil.copy(request.args.source, "/backups/")
