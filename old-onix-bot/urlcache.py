import os
import shutil
import sys
import time
import traceback
import urllib
from fcntl import *


class URLCache:
    def __init__(self, dir):
        self.dir = dir

    def get_entries(self):
        entries = {}
        index_file = self.dir + "/index"
        next = 0
        index = open(index_file, "a")  # create index file if it doesn't exist
        index.close()
        index = open(index_file, "r+")
        flock(index, LOCK_EX)

        for url in index:
            entries[url.rstrip()] = next
            next += 1
        return (entries, next, index)

    def get(self, url):
        url = url.strip()
        (entries, next, index) = self.get_entries()
        id = entries.get(url)
        if id is None:
            # with index locked, add an entry for this url and
            # open a locked, temporary file to load its data
            index.seek(0, 2)
            index.write(f"{url}\n")
            data_file = self.dir + "/" + str(next)
            tmp_data_file = data_file + "-fetching"
            tmp_data = open(tmp_data_file, "w")
            flock(tmp_data, LOCK_EX)
            index.close()

            # having released the lock on the index, suck data
            # into the temporary file
            sys.stderr.write(f"URLCache: fetching {url}\n")
            net_data = urllib.urlopen(url)
            shutil.copyfileobj(net_data, tmp_data)
            tmp_data.flush()
            os.link(tmp_data_file, data_file)  # the fetch is good: attach it
            tmp_data.close()  # drop lock on temporary file
            os.unlink(tmp_data_file)
            id = next

        else:
            # there is already an entry for this url, so release the lock on the index
            index.close()

        data_file = self.dir + "/" + str(id)
        if os.path.exists(data_file):
            return open(data_file)
        else:
            # wait for fetch to finish
            tmp_data_file = data_file + "-fetching"
            sys.stderr.write(f"URLCache: waiting for {data_file}\n")
            try:
                try:
                    tmp_data = open(tmp_data_file)
                    flock(tmp_data, LOCK_SH)
                    tmp_data.close()
                except OSError as e:
                    pass
                return open(data_file)
            except Exception as exn:
                # in case this happens, just blow away your cache
                raise Exception(
                    f"URLCache: sorry, corrupted state for url '{url}': {str(exn)}"
                )
