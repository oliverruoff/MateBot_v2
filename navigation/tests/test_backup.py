import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]))
from restore_backup import restore_archive


class ArchiveValidationTests(unittest.TestCase):
    def test_reject_path_traversal_symlinks_and_duplicate_entries(self):
        for bad_name,kind in [('../escape','file'),('snapshot/house.data','link'),('session.json','duplicate')]:
            with tempfile.TemporaryDirectory() as directory:
                archive_path=Path(directory)/'bad.tar.gz'
                with tarfile.open(archive_path,'w:gz') as archive:
                    entry=tarfile.TarInfo(bad_name)
                    if kind=='link':entry.type=tarfile.SYMTYPE;entry.linkname='/etc/passwd';archive.addfile(entry)
                    else:
                        entry.size=2;archive.addfile(entry,io.BytesIO(b'{}'))
                        if kind=='duplicate':archive.addfile(entry,io.BytesIO(b'{}'))
                destination=Path(directory)/'restore'
                with self.assertRaises(ValueError):restore_archive(archive_path,destination)
                self.assertFalse((Path(directory)/'escape').exists())
                self.assertFalse((destination/'session.json').exists())


if __name__=='__main__':unittest.main()
