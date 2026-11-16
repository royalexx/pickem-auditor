"""Opt-in local Poppler extraction for Debian Bookworm; never apt install/global update."""
import argparse,hashlib,json,os,pathlib,subprocess

def setup(prefix):
    root=pathlib.Path(prefix).resolve();root.mkdir(parents=True,exist_ok=False)
    lists=root/'apt-lists';(lists/'partial').mkdir(parents=True)
    opts=['-o','Dir::State::lists='+str(lists),'-o','APT::Get::List-Cleanup=0']
    def run(args):subprocess.run(args,cwd=root,check=True,timeout=90)
    run(['apt-get',*opts,'update'])
    run(['apt-get',*opts,'download','poppler-utils','libpoppler126','libnss3','libnspr4'])
    packages=[]
    for deb in sorted(root.glob('*.deb')):
        packages.append({'file':deb.name,'sha256':hashlib.sha256(deb.read_bytes()).hexdigest()})
        run(['dpkg-deb','-x',str(deb),str(root/'extracted')])
    env={**os.environ,'PATH':str(root/'extracted/usr/bin')+':'+os.environ['PATH'], 'LD_LIBRARY_PATH':str(root/'extracted/usr/lib/x86_64-linux-gnu')}
    subprocess.run(['pdftotext','-v'],env=env,check=True,timeout=10)
    with (root/'receipt.json').open('x') as f:json.dump({'packages':packages,'scope':'local extracted Debian Bookworm packages; no system install'},f,indent=2)
    print('export PATH="'+str(root/'extracted/usr/bin')+':$PATH"')
    print('export LD_LIBRARY_PATH="'+str(root/'extracted/usr/lib/x86_64-linux-gnu')+'"')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);setup(p.parse_args().prefix)
