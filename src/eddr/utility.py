
import hashlib
import os
import sys

def getAppDir() -> str:
    if sys.platform == 'win32':
        user_path = os.environ.get('USERPROFILE')
        assert user_path is not None
        return os.path.join(user_path, 'AppData', 'Roaming', 'YuiYukihira', 'Elite Dangerous Data Reporter')
    elif sys.platform == 'linux' or sys.platform == 'darwin':
        user_path = os.path.expanduser('~')
        return os.path.join(user_path, '.config', 'YuiYukihira', 'Elite Dangerous Data Reporter')
    raise Exception('Your OS is not supported')

def getResourcePath(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def getPluginPaths() -> list[str]:
    preinstalled_path = getResourcePath('plugins')
    extras = os.path.join(getAppDir(), 'plugins')
    return [preinstalled_path, extras]

def getJournalPath() -> str:
    if sys.platform == 'win32':
        user_path = os.environ.get('USERPROFILE')
        assert user_path is not None
        return os.path.join(user_path, 'Saved Games', 'Frontier Developments', 'Elite Dangerous')
    elif sys.platform == 'linux':
        user_path = os.path.expanduser('~')
        return os.path.join(user_path, '.local', 'share', 'Steam', 'steamapps', 'compatdata', '359320', 'pfx', 'drive_c', 'users', 'steamuser', 'Saved Games', 'Frontier Developments', 'Elite Dangerous')
    else:
        return None

def getCachePath(jr_version:str, journal_paths:list[str]) -> str|None:
    cache_dir = getAppDir()
    if cache_dir is None:
        return None
    else:
        try:
            h = hashlib.sha256()
            h.update(sys.platform.encode('utf-8'))
            for journal_path in journal_paths:
                h.update(journal_path.encode('utf-8'))
            return os.path.join(cache_dir, 'cache', f'journal_reader_{jr_version}_{h.hexdigest()}.pkl')
        except:
            return None
