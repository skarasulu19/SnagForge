"""Application icon and its per-user desktop launcher registration."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
ICON=ROOT/'assets'/'snagforge.png'


def desktop_quote(value):
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'


def register_desktop_icon(directory=None):
    """Refresh our own launcher while preserving any customized Exec command."""
    try:
        folder=Path(directory) if directory is not None else Path.home()/'.local/share/applications'
        folder.mkdir(parents=True,exist_ok=True)
        desktop=folder/'snagforge.desktop'
        if desktop.exists():
            lines=desktop.read_text().splitlines()
            if 'Name=SnagForge' not in lines:return False
            section=False;updated=False;result=[]
            for line in lines:
                if line.startswith('['):
                    if section and not updated:result.append('Icon='+str(ICON));updated=True
                    section=line=='[Desktop Entry]'
                if section and line.startswith('Icon='):
                    line='Icon='+str(ICON);updated=True
                result.append(line)
            if section and not updated:result.append('Icon='+str(ICON))
            content='\n'.join(result)+'\n'
        else:
            content=('[Desktop Entry]\nType=Application\nName=SnagForge\nComment=Capture. Annotate. Explain.\n'
                     'Exec='+desktop_quote(sys.executable)+' '+desktop_quote(ROOT/'app.py')+'\n'
                     'Icon='+str(ICON)+'\nTerminal=false\nCategories=Graphics;AudioVideo;\nStartupNotify=true\n')
        desktop.write_text(content);return True
    except OSError:
        # A read-only launcher directory must not prevent the app from opening.
        return False
