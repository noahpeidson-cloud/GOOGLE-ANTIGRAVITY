import zipfile
import os

def zipdir(path, ziph, arcname_prefix=''):
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.join(arcname_prefix, os.path.relpath(file_path, path))
            ziph.write(file_path, arcname)

with zipfile.ZipFile(r'd:\GOOGLE ANTIGRAVITY\.archive\media_pipeline_handoff.zip', 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zipf:
    zipdir(r'd:\GOOGLE ANTIGRAVITY\content_creation', zipf, arcname_prefix='content_creation')
    zipdir(r'C:\Users\noahp\.gemini\antigravity-ide\brain\26e9857c-0b51-4957-9495-97e0780aaf2e', zipf, arcname_prefix='brain_artifacts')
print('Done compressing.')
