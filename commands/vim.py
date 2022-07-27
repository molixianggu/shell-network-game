import time
import os

from suplemon.file import File
import suplemon.main

from commands.status import HostNode, TreeSystem
from pb.game_status_pb2 import FileType


class VFile(File):
    status: HostNode = None

    def on_load(self):
        """Does checks after file is loaded."""
        return True
        # self.writable = os.access(self._path(), os.W_OK)
        # if not self.writable:
        #     self.logger.info("File not writable.")

    def save(self):
        """Write the editor data to file."""
        data = self.editor.get_data()
        tree = self.status.file_sys.find(self.status.path[1:])
        obj = tree.index.get(self.name)
        if obj is None:
            tree.add(TreeSystem(self.name, FileType.txt, data))
        else:
            obj.data = data
        self.data = data
        self.last_save = time.time()
        # self.writable = os.access(self._path(), os.W_OK)
        return True

    def load(self, read=True):
        """Try to read the actual file and load the data into the editor instance."""
        if not read:
            return True
        tree = self.status.file_sys.find(self.status.path[1:])

        if tree.index.get(self.name) is None:
            return False

        # if not os.path.isfile(path):
        #     self.logger.debug("Given path isn't a file.")
        #     return False
        data = self._read(self.name)

        if data is False:
            return False
        self.data = data
        self.editor.set_data(data)
        self.on_load()
        return True

    def _read_text(self, file):
        # Read text file
        tree = self.status.file_sys.find(self.status.path[1:]).index.get(file)
        if tree is None or tree.type != FileType.txt:
            return False
        return tree.data

    def _read_binary(self, file):
        # Read binary file and try to autodetect encoding
        raise Exception("the file is not editable")


suplemon.main.File = VFile
os.environ["TERM"] = ""
