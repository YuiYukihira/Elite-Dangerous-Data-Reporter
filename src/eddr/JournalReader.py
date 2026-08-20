
from datetime import datetime, timedelta
import hashlib
import inspect
import json
import os
from os import path
import pickle
from queue import Empty, Queue
import re
from typing import Any, NamedTuple

from eddr.utility import getCachePath


class JournalReader:
    @classmethod
    def version_hash(cls) -> str:
        src = inspect.getsource(cls)
        return hashlib.sha256(src.encode('utf-8')).hexdigest()

    @staticmethod
    def load_from_cache(version:str, journal_paths:list[str]) -> 'JournalReader | None':
        cache_path = getCachePath(version, journal_paths)
        if cache_path and os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    jr:JournalReader = pickle.load(f)
                return jr
            except Exception:
                # something went wrong, assume cache is invalid
                try:
                    os.remove(cache_path)
                except OSError:
                    pass
        return None

    def __init__(self, journal_paths:list[str]):
        self.journal_paths = journal_paths

        self.journal_processed = []

        self.journal_latest_known_fids: dict[str, 'JournalReader.Journal'] = {}
        self.journal_latest_unknown_fids: dict[str, 'JournalReader.Journal'] = {}

        self.processable_items = Queue()

    class Journal(NamedTuple):
        filename: str
        line_pos: int
        is_active: bool

    def read_journals(self):
        latest_journal_info = {}
        for key, value in self.journal_latest_known_fids.items():
            latest_journal_info[value.filename] = {
                'fid': key,
                'line_pos': value.line_pos,
                'is_active': value.is_active
            }
        journals = []
        for journal_path in self.journal_paths:
            files = os.listdir(journal_path)
            r = r'^Journal\.\d{4}-\d{2}-\d{2}T\d{6}\.\d{2}\.log$'
            journal_files = sorted([i for i in files if re.fullmatch(r, i)], reverse=False)
            assert len(journal_files) > 0, f'No journal files found in {journal_path}'
            journals += [path.join(journal_path, i) for i in journal_files]
        for journal in journals:
            if journal not in self.journal_processed:
                self._read_journal(journal)
            elif journal in latest_journal_info.keys():
                if latest_journal_info[journal]['is_active']:
                    self._read_journal(journal, latest_journal_info[journal]['line_pos'], latest_journal_info[journal]['fid'])
            elif journal in self.journal_latest_unknown_fids.keys():
                self._read_journal(journal, self.journal_latest_unknown_fids[journal].line_pos)

    def read_market_for_fid(self, fid:str) -> dict[str, Any]|None:
        journal_file = self.journal_latest_known_fids[fid].filename
        journal_dir = os.path.dirname(journal_file)
        market_file = os.path.join(journal_dir, 'Market.json')

        
        with open(market_file, 'r', encoding='utf-8') as f:
            lines = f.read()
            try:
                return json.loads(lines)
            except json.decoder.JSONDecodeError as e:
                print('{market_file} {e}')
                return None

    def get_latest_active_journals(self) -> dict[str, str]|None:
        results = {}
        for fid, info in self.journal_latest_known_fids.items():
            if info.is_active:
                results[fid] = info.filename
        return results if results else None

    def _read_journal(self, journal_path:str, line_pos:int|None=None, fid_last:str|None=None):
        items=[]
        with open(journal_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            line_pos_new = len(lines)
            lines = lines[line_pos:]
            for i in lines:
                try:
                    items.append(json.loads(i))
                except json.decoder.JSONDecodeError as e:
                    print(f'{journal_path} {e}')
                    continue
        parsed_fid, is_active, items = self._parse_items(items, fid_last)
        if fid_last is None:
            fid = parsed_fid
        elif parsed_fid is not None and parsed_fid != fid_last:
            fid = None
        else:
            fid = fid_last
        if is_active:
            if fid is None:
                match = re.search(r'\d{4}-\d{2}-\d{2}T\d{6}', journal_path)
                assert match is not None
                if datetime.now() - datetime.strptime(match.group(0), '%Y-%m-%dT%H%M%S') < timedelta(hours=1):
                    self.journal_latest_unknown_fids[journal_path] = self.Journal(journal_path, line_pos or 0, is_active)
                else:
                    self.journal_latest_unknown_fids.pop(journal_path, None)
            else:
                self.journal_latest_unknown_fids.pop(journal_path, None)
                self.journal_latest_known_fids[fid] = self.Journal(journal_path, line_pos_new, is_active)
                for item in items:
                    self.processable_items.put(item)
        else:
            self.journal_latest_unknown_fids.pop(journal_path, None)
            if fid is not None:
                self.journal_latest_known_fids[fid] = self.Journal(journal_path, line_pos_new, is_active)
        if journal_path not in self.journal_processed:
            self.journal_processed.append(journal_path)

    def _parse_items(self, items:list, fid_last:str|None=None) -> tuple[str|None, bool, list]:
        fid_parsed = None
        fid_temp = [i['FID'] for i in items if i['event'] == 'Commander']
        if len(fid_temp) > 0:
            if all(i == fid_temp[0] for i in fid_temp):
                fid_parsed = fid_temp[0]
        fid = fid_parsed if fid_parsed is not None else fid_last

        is_active = len(items) == 0 or items[-1]['event'] != 'Shutdown'

        parsed_items = []
        if is_active:
            for item in items:
                item['FID'] = fid
                parsed_items.append(item)
        return fid_parsed, is_active, parsed_items