"""Prepare an isolated Colab experiment from the real worker (never execute it).

Example: python scripts/build_conditioning_experiment.py --case semantic-shirt-1
  --hostname VERIFIED_HOST --person PRIVATE.png --garment PRIVATE.png
  --output .runtime/semantic-shirt-cell.json

The resulting private cell must use the existing authenticated notebook helper.
It requires the installed worker/models, verifies source hashes and free GPU
memory, and never edits production configuration or restarts a runtime.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_program(case: str, mode: str = "semantic", validation_person: bool = False,
                  validation_baseline: bool = True, category: str = "shirt", photo_type: str = "model") -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", case):
        raise ValueError("Use a simple unique experiment name.")
    if mode not in {"semantic", "contour", "foreground", "preserve-bottoms"}:
        raise ValueError("Unknown diagnostic conditioning mode.")
    from ml.vton.categories import MODEL_CATEGORIES
    if MODEL_CATEGORIES.get(category) != "tops" or photo_type not in {"model", "flat-lay"}:
        raise ValueError("This conditioning experiment requires supported upper-body inputs.")
    variant = {"semantic": "E-semantic-shirt", "contour": "F-official-contour",
               "foreground": "G-foreground-contour",
               "preserve-bottoms": "H-preserve-bottoms"}[mode]
    method = ("FASHN label 3 only; neutral 127; no expansion" if mode == "semantic" else
              "Official agnostic; mask_limbs=False; min_distance_threshold=0; other defaults unchanged")
    if mode in {"foreground", "preserve-bottoms"}:
        method += "; preserve original parser-background pixels"
    if mode == "preserve-bottoms":
        method += "; preserve original skirt/pants/belt pixels"
    tree = ast.parse((ROOT / "scripts/online_worker.py").read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    ui = next(i for i, n in enumerate(main.body) if isinstance(n, ast.With)
              and "gr.Blocks" in ast.unparse(n.items[0].context_expr))
    helper = (ROOT / "ml/vton/person_conditioning.py").read_text()
    helper_tree = ast.parse(helper)
    helper_function = next(n for n in helper_tree.body if isinstance(n, ast.FunctionDef))
    main.body = main.body[:ui] + [helper_function] + ast.parse(f'''
import fashn_vton.pipeline as official_pipeline
case = root / 'experiments' / {case!r}
def semantic_condition(*, img_np, seg_pred, body_coverage, **kwargs):
    if body_coverage != 'upper':
        raise ValueError('This isolated trial supports only upper-body conditioning')
    return upper_clothing_conditioning(img_np, seg_pred)
official_pipeline.create_clothing_agnostic_image = semantic_condition
if {mode!r} in ('contour', 'foreground', 'preserve-bottoms'):
    from functools import partial
    from fashn_vton.preprocessing.agnostic import create_clothing_agnostic_image
    official_pipeline.create_clothing_agnostic_image = partial(
        create_clothing_agnostic_image, mask_limbs=False, min_distance_threshold=0)
    if {mode!r} in ('foreground', 'preserve-bottoms'):
        contour_condition = official_pipeline.create_clothing_agnostic_image
        def foreground_condition(*, img_np, seg_pred, **kwargs):
            original = img_np.copy()
            result = contour_condition(img_np=img_np, seg_pred=seg_pred, **kwargs)
            preserve = np.isin(seg_pred, [0, 5, 6, 7]) if {mode!r} == 'preserve-bottoms' else seg_pred == 0
            result[preserve] = original[preserve]
            return result
        official_pipeline.create_clothing_agnostic_image = foreground_condition
segmentation_free = False
environment['segmentationFree'] = False
environment['personConditioning'] = {method!r}
selected_conditioning = official_pipeline.create_clothing_agnostic_image
trials = [({variant!r}, 'person.png', False)]
if {validation_person!r}:
    if {validation_baseline!r}:
        trials += [('validation-baseline', 'validation-person.png', True)]
    trials += [('validation-' + {variant!r}, 'validation-person.png', False)]
for trial_name, person_name, baseline in trials:
    segmentation_free = baseline
    environment['segmentationFree'] = baseline
    environment['personConditioning'] = 'unmasked baseline' if baseline else {method!r}
    official_pipeline.create_clothing_agnostic_image = (lambda **kw: kw['img_np']) if baseline else selected_conditioning
    started = time.perf_counter()
    payload = generate(token,
        base64.b64encode((case/person_name).read_bytes()).decode(),
        base64.b64encode((case/'garment.png').read_bytes()).decode(),
        {category!r}, {photo_type!r}, 10)
    payload.pop('image', None)
    payload['experiment'] = {{'variant':trial_name, 'elapsedSeconds':time.perf_counter()-started,
        'personConditioning':environment['personConditioning']}}
    if payload.get('runPath'):
        raw = Path(payload['runPath'])/'raw.png'
        payload['experiment']['rawSha256'] = hashlib.sha256(raw.read_bytes()).hexdigest() if raw.is_file() else None
    (case/(trial_name+'.json')).write_text(json.dumps(payload, indent=2))
    print(json.dumps({{'status':'failed' if payload.get('error') else 'generated','runPath':payload.get('runPath')}}),flush=True)
''').body
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value in {"active-generation.json", "worker-environment.json"}:
            node.value = f"experiments/{case}/{node.value}"
    program = ast.unparse(ast.fix_missing_locations(tree))
    compile(program, "<conditioning-experiment>", "exec")
    return program


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--mode", choices=["semantic", "contour", "foreground", "preserve-bottoms"], default="semantic")
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--person", type=Path, required=True)
    parser.add_argument("--garment", type=Path, required=True)
    parser.add_argument("--category", default="shirt")
    parser.add_argument("--photo-type", choices=["model", "flat-lay"], default="model")
    parser.add_argument("--validation-person", type=Path)
    parser.add_argument("--reuse-validation-baseline", action="store_true",
                        help="Reuse an already saved exact-input/config baseline instead of generating it again")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", args.hostname):
        parser.error("Supply the independently verified runtime hostname.")
    program = build_program(args.case, args.mode, bool(args.validation_person),
                            not args.reuse_validation_baseline, args.category, args.photo_type)
    records = {}
    from PIL import Image
    inputs = [("person.png", args.person), ("garment.png", args.garment)]
    if args.validation_person:
        inputs.append(("validation-person.png", args.validation_person))
    for name, path in inputs:
        with Image.open(path) as image:
            if image.format != "PNG" or image.mode != "RGB" or min(image.size) < 128 or image.width * image.height > 2_000_000:
                parser.error("Use the saved RGB PNG inference inputs without re-encoding.")
            image.verify()
        data = path.read_bytes()
        records[name] = {"sha256": hashlib.sha256(data).hexdigest(), "data": base64.b64encode(data).decode()}
    source_hash = hashlib.sha256((ROOT / "scripts/online_worker.py").read_bytes()).hexdigest()
    code = f'''
import base64, hashlib, json, os, socket, subprocess
from pathlib import Path
root=Path('/content/formfit-online')
assert socket.gethostname()=={args.hostname!r}, 'Runtime changed; verify before running'
assert hashlib.sha256((root/'scripts/online_worker.py').read_bytes()).hexdigest()=={source_hash!r}, 'Worker source mismatch'
assert (root/'setup-complete.json').is_file(), 'Existing installation required'
assert not (root/'active-generation.json').exists(), 'Preserve active production inference'
free=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()[0])
assert free>6500, 'Insufficient spare VRAM; preserve loaded production worker'
case=root/'experiments'/{args.case!r}
case.mkdir(parents=True,exist_ok=False)
for name,record in {records!r}.items():
    data=base64.b64decode(record['data'],validate=True)
    assert hashlib.sha256(data).hexdigest()==record['sha256']
    (case/name).write_bytes(data)
script=root/'scripts'/{('experiment_'+args.case+'.py')!r}
with script.open('xb') as f:
    f.write(base64.b64decode({base64.b64encode(program.encode()).decode()!r}))
with (case/'setup.log').open('x') as log:
    process=subprocess.Popen([str(root/'.venv/bin/python'),'-u',str(script)],cwd=root,
        stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={{**os.environ,'USE_TF':'0'}})
(case/'pid.json').write_text(json.dumps({{'pid':process.pid,'sourceSha256':{source_hash!r}}}))
print(json.dumps({{'started':True,'pid':process.pid,'freeMemoryMB':free}}))
'''
    compile(code, "<private-colab-cell>", "exec")
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump({"cellIndex": 1, "language": "python", "code": code}, stream)
    print(json.dumps({"prepared": True, "executed": False, "output": str(args.output)}))


if __name__ == "__main__":
    main()
