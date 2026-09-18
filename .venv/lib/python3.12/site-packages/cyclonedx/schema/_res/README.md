# Resources: Schema files

some schema for offline use as downloaded via [script](../../../tools/schema-downloader.py).
original sources: <https://github.com/CycloneDX/specification/tree/master/schema>

Currently using version
[b29bae660048e0ad2fbc5f2972927b442ce951c4](https://github.com/CycloneDX/specification/commit/b29bae660048e0ad2fbc5f2972927b442ce951c4)

| file | note |
|------|------|
| [`bom-1.0.SNAPSHOT.xsd`](bom-1.0.SNAPSHOT.xsd) | applied changes: 1 |
| [`bom-1.1.SNAPSHOT.xsd`](bom-1.1.SNAPSHOT.xsd) | applied changes: 1 |
| [`bom-1.2.SNAPSHOT.xsd`](bom-1.2.SNAPSHOT.xsd) | applied changes: 1 |
| [`bom-1.3.SNAPSHOT.xsd`](bom-1.3.SNAPSHOT.xsd) | applied changes: 1 |
| [`bom-1.4.SNAPSHOT.xsd`](bom-1.4.SNAPSHOT.xsd) | applied changes: 1 |
| [`bom-1.5.SNAPSHOT.xsd`](bom-1.5.SNAPSHOT.xsd) | applied changes: 1 |
| [`bom-1.6.SNAPSHOT.xsd`](bom-1.6.SNAPSHOT.xsd) | applied changes: 1 |
| [`bom-1.7.SNAPSHOT.xsd`](bom-1.7.SNAPSHOT.xsd) | applied changes: 1 |
| [`bom-1.2.SNAPSHOT.schema.json`](bom-1.2.SNAPSHOT.schema.json) | applied changes: 2,3,4,5,6 |
| [`bom-1.3.SNAPSHOT.schema.json`](bom-1.3.SNAPSHOT.schema.json) | applied changes: 2,3,4,5,6 |
| [`bom-1.4.SNAPSHOT.schema.json`](bom-1.4.SNAPSHOT.schema.json) | applied changes: 2,3,4,5,6 |
| [`bom-1.5.SNAPSHOT.schema.json`](bom-1.5.SNAPSHOT.schema.json) | applied changes: 2,3,4,5,6 |
| [`bom-1.6.SNAPSHOT.schema.json`](bom-1.6.SNAPSHOT.schema.json) | applied changes: 2,3,4,5,6 |
| [`bom-1.7.SNAPSHOT.schema.json`](bom-1.7.SNAPSHOT.schema.json) | applied changes: 2,3,4,5,6,7 |
| [`bom-1.2-strict.SNAPSHOT.schema.json`](bom-1.2-strict.SNAPSHOT.schema.json) | applied changes: 2,3,4,5,6 |
| [`bom-1.3-strict.SNAPSHOT.schema.json`](bom-1.3-strict.SNAPSHOT.schema.json) | applied changes: 2,3,4,5,6 |
| [`spdx.SNAPSHOT.xsd`](spdx.SNAPSHOT.xsd) | |
| [`spdx.SNAPSHOT.schema.json`](spdx.SNAPSHOT.schema.json) | |
| [`cryptography-defs.SNAPSHOT.schema.json`](cryptography-defs.SNAPSHOT.schema.json) | |
| [`jsf-0.82.SNAPSHOT.schema.json`](jsf-0.82.SNAPSHOT.schema.json) | |

changes:
1. `https?://cyclonedx.org/schema/spdx` was replaced with `spdx.SNAPSHOT.xsd`
2. `spdx.schema.json` was replaced with `spdx.SNAPSHOT.schema.json`
3. `jsf-0.82.schema.json` was replaced with `jsf-0.82.SNAPSHOT.schema.json`
4. `properties.$schema.enum` was removed
5. `required.version` removed, as it is actually optional with default value
6. `"pattern": "^(.*)$"` removed as it has no meaning
7. `cryptography-defs.schema.json` was replaced with `cryptography-defs.SNAPSHOT.schema.json`

