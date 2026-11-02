"""Measure retained online runs without inference or modifying their images.

The reference parser mask and target clothing labels must come from the actual
worker. This reports catastrophic color changes and exact preservation regions;
it does not substitute for full-resolution visual review.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.vton.garment_fidelity import assess_dark_reference, fabric_statistics


def review(folder: Path) -> dict:
    def read(name):
        return np.array(Image.open(folder / name))
    original, generated = read('person-input.png'), read('raw.png')
    final = read('result.png')
    source, target = read('source-labels.png'), read('target-labels.png')
    reference, reference_labels = read('garment-input.png'), read('garment-labels.png')
    if (original.ndim != 3 or original.shape[-1] != 3
            or original.shape != generated.shape or original.shape != final.shape
            or source.shape != original.shape[:2] or target.shape != source.shape
            or reference_labels.shape != reference.shape[:2]):
        raise ValueError('Saved images and parsing maps must have matching dimensions')
    protected = np.isin(source, (1, 2, 8, 9, 11, 13, 15, 17))
    target_fabric = (target == 3) & ~protected
    measurements = assess_dark_reference(reference, reference_labels == 3, generated, target_fabric)
    final_measurements = assess_dark_reference(reference, reference_labels == 3, final, target_fabric)
    # A pale hem can be labelled background or a separate garment and therefore
    # disappear from the new-shirt-only check. Report the actual replaced region
    # separately; it may legitimately contain newly exposed skin/background.
    # Never use this broader diagnostic to reject or repaint those pixels.
    replaced = (source == 3) & ~protected
    labels, counts = np.unique(target[replaced], return_counts=True)
    replacement = {
        'rawAppearance': fabric_statistics(generated, replaced),
        'finalAppearance': fabric_statistics(final, replaced),
        'targetLabelPixels': {str(int(label)): int(count) for label, count in zip(labels, counts)},
        'rawToFinalChangedPixels': int(np.count_nonzero(np.any(generated != final, axis=2) & replaced)),
        'limitations': 'Original shirt footprint is not a new-garment mask; exposed skin or background can be legitimate. Visual review required.',
    }
    regions = {'face': source == 1, 'hair': source == 2, 'bag': source == 8,
               'hands': source == 13, 'jeans': source == 6, 'background': source == 0}
    changed = np.any(original != final, axis=2)
    return {'colorDiagnostic': measurements, 'compositedColorDiagnostic': final_measurements,
        'replacedRegionDiagnostic': replacement, 'preservation': {
        name: {'pixels': int(mask.sum()), 'changedPixels': int((mask & changed).sum())}
        for name, mask in regions.items()
    }, 'visualAcceptance': 'pending full-resolution inspection',
        'limitations': 'Parser errors affect these measurements. Non-rejection is not a garment-fidelity certificate.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    report = review(args.folder)
    (args.folder / 'fidelity-metrics.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
