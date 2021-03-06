import io
import sys
import asyncio
import aiohttp
from .errors import *
from typing import Any, Optional
from urllib.parse import quote_plus


class Route:

    __MIME_TYPE = 'application/json'
    __CONTENT_TYPE = 'application/octet-stream'
    __BASE = 'https://database.deta.sh/v1/'
    __DRIVE = 'https://drive.deta.sh/v1/'
    __SINGLE_REQ_UPLOAD_SIZE = 10485760  # 10MB

    def __init__(self, deta):
        self.__session = deta.session
        self.__project_id = deta.token.split('_')[0]
        self.__base_root = self.__BASE + self.__project_id + '/'
        self.__drive_root = self.__DRIVE + self.__project_id + '/'
        self.__base_headers = {'X-API-Key': deta.token, 'Content-Type': self.__MIME_TYPE}
        self.__drive_headers = {'X-API-Key': deta.token, 'Content-Type': self.__CONTENT_TYPE}

    @staticmethod
    def __err(error_map: dict) -> str:
        return '\n'.join(error_map['errors'])

    async def _close(self):
        await self.__session.close()

    async def _fetch(self, base_name: str, key: str):
        ep = self.__base_root + base_name + '/items/' + key
        resp = await self.__session.get(ep, headers=self.__base_headers)
        if resp.status == 200:
            return await resp.json()
        if resp.status == 404:
            return None

    async def _fetch_all(self, base_name: str):
        ep = self.__base_root + base_name + '/query'
        items = []
        ini_data = await (await self.__session.post(ep, headers=self.__base_headers)).json()
        last = ini_data['paging'].get('last')
        items.extend(ini_data['items'])
        while last:
            data = await (await self.__session.post(ep, headers=self.__base_headers, data={'last': last})).json()
            items.extend(data['items'])
            last = data['paging'].get('last')
        return items

    async def _put(self, base_name: str, json_data: dict):
        ep = self.__base_root + base_name + '/items'
        resp = await self.__session.put(ep, headers=self.__base_headers, json=json_data)
        if resp.status == 207:
            data = await resp.json()
            if 'failed' in data:
                print('Warning: some items failed because of internal processing error', file=sys.stderr)
        if resp.status == 400:
            e = await resp.json()
            raise BadRequest(e['errors'][0])
        return await resp.json()

    async def _delete(self, base_name: str, key: str):
        ep = self.__base_root + base_name + '/items/' + key
        await self.__session.delete(ep, headers=self.__base_headers)
        return key

    async def _delete_many(self, base_name: str, keys: list):
        task = [asyncio.create_task(self._delete(base_name, key)) for key in keys]
        return await asyncio.gather(*task)

    async def _insert(self, base_name: str, json_data: dict):
        ep = self.__base_root + base_name + '/items'
        resp = await self.__session.post(ep, headers=self.__base_headers, json=json_data)
        if resp.status == 201:
            return await resp.json()
        if resp.status == 409:
            raise KeyConflict('key already exists in Deta base')
        if resp.status == 400:
            raise BadRequest('invalid insert payload')

    async def _update(self, base_name: str, key: str, payload: dict):
        ep = self.__base_root + base_name + '/items/' + key
        resp = await self.__session.patch(ep, headers=self.__base_headers, json=payload)
        if resp.status == 200:
            return await resp.json()
        if resp.status == 404:
            raise NotFound('key does not exist in Deta Base')
        if resp.status == 400:
            raise BadRequest('invalid update payload')

    async def _query(self, base_name: str, limit: Optional[int], last: Optional[str], query: dict):
        ep = self.__base_root + base_name + '/query'
        if limit and limit > 1000:
            raise ValueError('limit must be less or equal to 1000')
        if limit and limit <= 0:
            raise ValueError('limit must be greater than 0')
        queries = []
        if isinstance(query, list):
            queries.extend(query)
        else:
            queries.append(query)
        payload = {'query': queries}
        items = []
        if last and not limit:
            payload['last'] = last
            ini_data = await (await self.__session.post(ep, headers=self.__base_headers, json=payload)).json()
            items.extend(ini_data['items'])
            last = ini_data['paging'].get('last')
            while last:
                data = await (await self.__session.post(ep, headers=self.__base_headers, json={'last': last})).json()
                items.extend(data['items'])
                last = data['paging'].get('last')
        elif not last and limit:
            payload['limit'] = limit
            resp = await self.__session.post(ep, headers=self.__base_headers, json=query)
            items.extend((await resp.json())['items'])
        elif last and limit:
            payload['last'] = last
            payload['limit'] = limit
            resp = await (await self.__session.post(ep, headers=self.__base_headers, json=query)).json()
            items.extend(resp['items'])
        else:
            ini_data = await (await self.__session.post(ep, headers=self.__base_headers, json=payload)).json()
            items.extend(ini_data['items'])
            last = ini_data['paging'].get('last')
            while last:
                payload['last'] = last
                resp = await (await self.__session.post(ep, headers=self.__base_headers, json=payload)).json()
                items.extend(resp['items'])
                last = resp['paging'].get('last')
        return items

    async def _fetch_file_list(
            self,
            drive_name: str,
            limit: Optional[int] = None,
            prefix: str = None,
            last: str = None,
    ):
        tail = f'/files?'
        if limit and limit > 1000:
            raise ValueError('limit must be less or equal to 1000')
        if limit and limit <= 0:
            raise ValueError('limit must be greater than 0')
        if limit:
            tail += f'limit={limit}'
        if prefix:
            tail += f'&prefix={prefix}'
        if last:
            tail += f'&last={last}'
        ep = self.__drive_root + drive_name + tail
        resp = await self.__session.get(ep, headers=self.__base_headers)
        if resp.status == 200:
            return await resp.json()
        if resp.status == 400:
            error_map = await resp.json()
            raise BadRequest('\n'.join(error_map['errors']))

    async def _bulk_delete_files(self, drive_name: str, keys: list):
        ep = self.__drive_root + drive_name + '/files'
        json_data = {'names': keys}
        resp = await self.__session.delete(ep, headers=self.__base_headers, json=json_data)
        return await resp.json()

    async def _push_file(self, drive_name: str, remote_path: str, file_path: str = None, content: Any = None):

        if file_path:
            with open(file_path, 'rb') as f:
                fp = io.BytesIO(f.read())
        elif isinstance(content, str):
            fp = io.StringIO(content)
        elif isinstance(content, bytes):
            fp = io.BytesIO(content)
        else:
            fp = io.BytesIO(b'')

        byte_chunk = fp.read()

        if not len(byte_chunk) > self.__SINGLE_REQ_UPLOAD_SIZE:
            ep = self.__drive_root + drive_name + '/files?name=' + quote_plus(remote_path)
            resp = await self.__session.post(ep, headers=self.__drive_headers, data=byte_chunk)
            if resp.status == 201:
                return await resp.json()
            elif resp.status == 400:
                error_map = await resp.json()
                raise BadRequest(self.__err(await resp.json()))
            else:
                error_map = await resp.json()
                raise Exception(self.__err(await resp.json()))

        ep = self.__drive_root + drive_name + '/uploads?name=' + quote_plus(remote_path)
        resp = await self.__session.post(ep, headers=self.__drive_headers)
        if resp.status == 202:
            upload_id = (await resp.json())['upload_id']
            chunked = [
                byte_chunk[i:i+self.__SINGLE_REQ_UPLOAD_SIZE]
                for i in range(0, len(byte_chunk), self.__SINGLE_REQ_UPLOAD_SIZE)
            ]
            uploads = []
            for i, chunk in enumerate(chunked[:-1]):
                post_ep = (
                    f"{self.__drive_root}{drive_name}/uploads/{upload_id}/parts?name={remote_path}&part={i+1}"
                )
                uploads.append(
                    asyncio.create_task(self.__session.post(post_ep, headers=self.__drive_headers, data=chunk))
                )
            gathered = await asyncio.gather(*uploads)
            for item in gathered:
                if isinstance(item, Exception):
                    abort_ep = f"{self.__drive_root}{drive_name}/uploads/{upload_id}?name={remote_path}"
                    resp = await self.__session.delete(abort_ep, headers=self.__drive_headers)
                    if resp.status == 200:
                        return await resp.json()
                    if resp.status == 400:
                        raise BadRequest(self.__err(await resp.json()))
                    if resp.status == 404:
                        raise NotFound(self.__err(await resp.json()))

            patch_ep = f"{self.__drive_root}{drive_name}/uploads/{upload_id}?name={remote_path}"
            resp = await self.__session.patch(patch_ep, headers=self.__drive_headers, data=chunked[-1])
            if resp.status == 200:
                return await resp.json()
            if resp.status == 400:
                raise BadRequest(self.__err(await resp.json()))
            if resp.status == 404:
                raise NotFound(self.__err(await resp.json()))

    async def _pull_file(self, drive_name, remote_path) -> bytes:
        ep = self.__drive_root + drive_name + f'/files/download?name={quote_plus(remote_path)}'
        resp = await self.__session.get(ep, headers=self.__drive_headers)
        if resp.status == 400:
            raise BadRequest(self.__err(await resp.json()))
        if resp.status == 404:
            raise NotFound(self.__err(await resp.json()))
        if resp.status == 200:
            return resp
