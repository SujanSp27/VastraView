# Immutable studio-person regression fixture

`studio-person.jpg` is the original public research sample already embedded in
the project's checked-in Colab notebook. It was recovered byte-for-byte from
that checksum-verified archive, not copied from a private upload.

- Existing source: `scripts/download_samples.py`, Unsplash photo
  `photo-1666358085605-b3b717d5a210` (`w=1000&q=90`).
- SHA-256: `1d450d545f08a2945217f76908d229c14381cd59bb3b8c936c1c0e1a938bad8f`.
- Purpose: unpaired visual regression only, not training data or measurement
  ground truth. The source attribution and existing research-use scope remain.

Keep this fixture separate from the user-selectable male sample. Changing an
application sample must not silently replace the input of a saved GPU experiment.
The Colab builder continues to enforce this exact checksum.
