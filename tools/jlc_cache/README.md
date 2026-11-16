# JLC / EasyEDA lookup cache

Footprint data already fetched from JLC's EasyEDA API
(`https://easyeda.com/api/products/<LCSC>/components?version=6.4.19.5`).
**Check `index.csv` here before fetching anything from JLC, LCSC or EasyEDA.**

- `index.csv`: LCSC number, EasyEDA footprint name, pad file, and the rotation offset
  this board uses (degrees, the `FT Rotation Offset` convention).
  **The offset depends on the KiCad footprint as well as the LCSC number.** For example,
  C910544 is 270 on FCL's `TQFN-16-1EP_3x3mm` but 0 on the ESP32S3 project's MAX98357
  footprint. Reuse the pad data, but redo the match for your own footprint.
- `easyeda/<LCSC>.json`: `head` (footprint origin) and `pads` as
  `[number, x, y, w, h, ...]`, in EasyEDA units (10 mil) with Y pointing down.
  Pad data was read through WebFetch, so check it before relying on fine detail.
- `easyeda_raw/<LCSC>.json`: full, unedited API responses (25 parts, contributed by the
  ESP32S3_Audio_Cam_POE session). Pads are the `PAD~` strings in
  `result.packageDetail.dataStr.shape`.
- "(title only)" rows were checked by hand; their pad lists are not saved.
- The `other projects` column gives offsets other projects found for their own footprints.

## Rate limit

On 2026-11-16, about 13 fetches in quick succession from three parallel agents
started getting HTTP 403 from easyeda.com. Single fetches a few minutes later worked.

- Fetch one part at a time, never from parallel agents.
- Add every new result here (file and `index.csv` row) so it is never fetched twice.
- Plain 2-pin R/C/L parts don't need fetching: the rotation offset is 0.
