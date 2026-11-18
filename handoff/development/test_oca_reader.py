"""Read generated OCA with an installed reader library, without loading Krita UI.

python3 development/test_oca_reader.py /path/to/OCA/oca_core document.oca [...]
This verifies the reader's data path, not GUI import, playback or save/reopen.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys


def main():
    sys.dont_write_bytecode = True
    core = Path(sys.argv[1]).resolve()
    spec = importlib.util.spec_from_file_location('oca_test_reader', core/'__init__.py',
                                                submodule_search_locations=[str(core)])
    reader = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reader
    spec.loader.exec_module(reader)
    for filename in sys.argv[2:]:
        path = Path(filename).resolve()
        document = reader.file.load(str(path))
        before = copy.deepcopy(document)
        reader.document.sanitize(document, str(path))
        assert before == document, 'Reader changed published metadata: '+str(path)
        def frames(nodes):
            for node in nodes:
                yield from node['frames']
                yield from frames(node.get('childLayers', []))
        cels = list(frames(document['layers']))
        for cel in cels:
            if cel['name'] == '_blank':
                assert cel['fileName'] == ''
            else:
                assert (path.parent/cel['fileName']).is_file(), cel['fileName']
            assert cel['duration'] > 0
        print(json.dumps(dict(document=str(path), reader=str(core), unchanged_metadata=True,
                              frames=len(cels), existing_assets=True)), flush=True)


if __name__ == '__main__':
    main()
