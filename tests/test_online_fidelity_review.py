import numpy as np
import pytest
from PIL import Image

from scripts.review_online_fidelity import review


def fixture(folder):
    source = np.zeros((160, 120), dtype=np.uint8)
    source[30:130, 30:90] = 3
    target = source.copy()
    target[110:130, 30:90] = 0
    original = np.full((160, 120, 3), 240, dtype=np.uint8)
    original[source == 3] = [190, 170, 155]
    raw = original.copy()
    raw[source == 3] = [70, 35, 30]
    final = raw.copy()
    final[110:130, 30:90] = 230
    reference = raw.copy()
    for name, array in {'person-input.png': original, 'raw.png': raw, 'result.png': final,
                        'source-labels.png': source, 'target-labels.png': target,
                        'garment-input.png': reference, 'garment-labels.png': source}.items():
        Image.fromarray(array).save(folder / name)


def test_review_exposes_final_hem_outside_generated_shirt_mask(tmp_path):
    fixture(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    report = review(tmp_path)
    assert report['colorDiagnostic']['status'] == 'not_rejected'
    assert report['compositedColorDiagnostic']['status'] == 'not_rejected'
    replacement = report['replacedRegionDiagnostic']
    assert replacement['rawAppearance']['paleFraction'] == 0
    assert replacement['finalAppearance']['paleFraction'] > .15
    assert replacement['targetLabelPixels']['0'] == 1200
    assert replacement['rawToFinalChangedPixels'] == 1200
    assert report['visualAcceptance'] == 'pending full-resolution inspection'
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_review_checks_final_shirt_and_does_not_certify_fit(tmp_path):
    fixture(tmp_path)
    Image.fromarray(np.full((160, 120, 3), 235, dtype=np.uint8)).save(tmp_path / 'result.png')
    report = review(tmp_path)
    assert report['compositedColorDiagnostic']['status'] == 'rejected'
    assert report['colorDiagnostic']['status'] == 'not_rejected'
    assert report['preservation']['background']['changedPixels'] > 0


def test_review_refuses_misaligned_artifacts(tmp_path):
    fixture(tmp_path)
    Image.new('RGB', (100, 100)).save(tmp_path / 'result.png')
    with pytest.raises(ValueError, match='matching dimensions'):
        review(tmp_path)
