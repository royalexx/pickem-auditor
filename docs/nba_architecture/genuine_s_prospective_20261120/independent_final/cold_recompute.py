"""Run archived inputs while denying all other reads in the original repository."""
from pathlib import Path
import runpy
import sys
archive=Path(sys.argv[1]).resolve();repository=Path(sys.argv[2]).resolve()
def guard(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=Path(args[0].decode() if isinstance(args[0],bytes) else args[0]).resolve()
        if path.is_relative_to(repository) and not path.is_relative_to(archive):
            raise PermissionError('ORIGINAL_REPOSITORY_ACCESS_FORBIDDEN:'+str(path))
sys.addaudithook(guard)
script=archive/'reader/scripts/nba_genuine_s.py'
sys.argv=[str(script),'_recompute-archive',str(archive)]
runpy.run_path(str(script),run_name='__main__')
