"""Ensure the experimental driver cannot silently drift from the real worker."""
import ast

import numpy as np
import pytest

from scripts.build_conditioning_experiment import ROOT, build_program


def test_reuses_production_generation_without_starting_server_or_touching_its_state():
    before = (ROOT / "scripts/online_worker.py").read_bytes()
    source = ast.parse(before)
    program = build_program("test-semantic")
    experiment = ast.parse(program)
    compile(program, "<test>", "exec")
    def generation(tree):
        return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "generate")
    original = generation(source)
    # Only isolate the active-job marker; the actual model path stays identical.
    for node in ast.walk(original):
        if isinstance(node, ast.Constant) and node.value == "active-generation.json":
            node.value = "experiments/test-semantic/active-generation.json"
    assert ast.dump(original) == ast.dump(generation(experiment))
    assert "gr.Blocks" not in program
    assert "root / 'worker-environment.json'" not in program
    assert "root / 'active-generation.json'" not in program
    assert "'shirt', 'model', 10" in program
    assert "segmentation_free = False" in program
    assert (ROOT / "scripts/online_worker.py").read_bytes() == before


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/b", "", "x" * 65])
def test_experiment_names_cannot_escape_private_directory(name):
    with pytest.raises(ValueError):
        build_program(name)


def test_flat_lay_experiment_does_not_silently_switch_to_worn_reference():
    program = build_program("striped-reference", category="shirt", photo_type="flat-lay")
    assert "'shirt', 'flat-lay', 10" in program
    with pytest.raises(ValueError, match="upper-body"):
        build_program("invalid", category="dress")


@pytest.mark.parametrize("mode,kept", [("foreground", [0]), ("preserve-bottoms", [0, 5, 6, 7])])
def test_foreground_comparison_restores_only_specified_observed_regions(mode, kept):
    tree = ast.parse(build_program("foreground-test", mode, True))
    function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "foreground_condition")
    def contour_condition(*, img_np, **kwargs):
        img_np[:] = 127
        return img_np
    scope = {"contour_condition": contour_condition, "np": np}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<wrapper>", "exec"), scope)
    labels = np.array([[0, 3, 5], [12, 6, 7]], dtype=np.uint8)
    image = np.full((2, 3, 3), 220, dtype=np.uint8)
    result = scope["foreground_condition"](img_np=image.copy(), seg_pred=labels)
    assert np.all(result[np.isin(labels, kept)] == 220)
    assert np.all(result[~np.isin(labels, kept)] == 127)
    # The comparison changes only foreground restriction, not upstream mask size.
    assert "min_distance_threshold=0" in ast.unparse(tree)
    assert "mask_limbs=False" in ast.unparse(tree)
