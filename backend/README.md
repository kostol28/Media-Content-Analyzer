# Backend upload fix (Meltwater CSV)

If upload parsing fails with:

`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0`

the file is likely UTF-16 encoded (common for Meltwater exports). Use
`read_uploaded_csv` from `app/api/csv_utils.py` and replace direct calls to
`pd.read_csv(file.file)` with:

```python
from app.api.csv_utils import read_uploaded_csv

df = read_uploaded_csv(file.file)
```

This helper tries `utf-8-sig`, `utf-16`, `utf-16-le`, and `latin-1`.
