asyncdeta
==========

An async library to interact with deta.sh base & drive

- `Discord <https://discord.gg/bh99VTt9dH>`_
- `GitHub <https://github.com/jnsougata>`_

Table of Contents
=================
- `Installation <#installing>`_
- `Quick Start <#quick-start>`_
- `Usage <#usage>`_
- `Base <#base>`_
- `Drive <#drive>`_


Installing
----------

**Python 3.6 or higher is required**

.. code:: sh

    pip install git+https://github.com/jnsougata/async-deta

Quick Start
--------------

.. code:: py

    # interacting with deta drive & base

    import os
    import asyncio
    from asyncdeta import Deta, Field


    async def main():

        deta = Deta(os.getenv("PROJECT_KEY"))

        # mandatory to assign a session
        await deta.connect()

        # instantiating a drive
        drive = deta.drive(name='test_123')

        # instantiating a base
        base = deta.base(name='test_123')

        # storing a json obj to deta base
        await base.put(key='test', field=Field(name='abc', value={'a': 1, 'b': 2}))

        # downloading a song stored in deta drive
        resp = await drive.get(file_name='song.mp3')
        with open('song.mp3', 'wb') as f:
            f.write(resp.read())

        # closing deta connection
        await deta.close()


    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())

Usage
------

Base
~~~~~~
.. csv-table::
   :header: "Method", "Return Type", "Description"
   :widths: 200, 100, 200

   "add_field(key: str, field: Field, force: bool = False)", "Dict[str, Any]", "Adds a field to an existing key. If field already exists, old value will be overwritten."
   "remove_field(self, key: str, field_name: str)", "Dict[str, Any]", "Removes a field from an existing key."
   "fetch(key: str)", "Dict[str, Any]", "Fetches a single item from base by key."
   "multi_fetch(*keys: str)", "List[Dict[str, Any]]", "Fetches multiple items from base."
   "fetch_all()", "List[Dict[str, Any]]", "Fetches all items from a base."
   "put(key: str, field: Field, *, expire_at: datetime = None, expire_after: Union[int, float] = None)", "Dict[str, Any]", "Adds a field to base with given key. If key already exists, old value will be overwritten."
   "put_many(key: str, fields: List[Field], *, expire_at: datetime = None, expire_after: Union[int, float] = None)", "List[Dict[str, Any]]", "Adds multiple fields to single key in a base. If key already exists, old value will be overwritten."
   "put_bulk(key: str, fields: List[List[Field]], *, expire_ats: List[datetime] = None, expire_afters: List[Union[int, float]] = None)", "List[Dict[str, Any]]", "Adds multiple fields to multiple keys in a base. If keys already exist, old value will be overwritten."
   "insert(key: str, field: Field)", "Dict[str, Any]", "Creates a field to base with given key if any field with same key doesn't exist."
   "insert_many(key: str, fields: List[Field])", "Dict[str, Any]", "Creates multiple fields to single key in a base if any field with same key doesn't exist."
   "update(key: str, updates: List[Update])", "Dict[str, Any]", "Updates a field only if a field with given key exists."
   "delete(key: str)", "Dict[str, Any]", "Deletes single key from a base."
   "delete_many(*keys: tuple[str])", "Dict[str, Any]", "Deletes multiple keys from a base."

Drive
~~~~~~
.. csv-table::
   :header: "Method", "Return Type", "Description"
   :widths: 200, 100, 200

   "files(limit: int = None, prefix: str = None)", "List[str]", "Fetches all filenames from a drive if limit is not specified"
   "delete(file_name: str)", "Dict[str, Any]", "Deletes a file from a drive by file name."
   "delete_many(*file_names: tuple[str])", "Dict[str, Any]", "Deletes multiple files from a drive by file names."
   "upload(file_name: str, *, path: str = None, content: Union[bytes, str] = None)", "Dict[str, Any]", "Uploads a file to a drive."
   "get(file_name: str)", "io.BytesIO", "Downloads a file from a drive by file name."
