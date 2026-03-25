import pandas as pd
import json

try:
    df_all = pd.read_excel('PARAMETRIZACIÓN 2026.xlsx', sheet_name=None, dtype=str)
    output = {}
    for sheet_name, df in df_all.items():
        df_clean = df.fillna("").head(20)
        output[sheet_name] = {
            "columns": df.columns.tolist(),
            "data": df_clean.to_dict('records')
        }
    with open('param_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
except Exception as e:
    print(f"Error: {e}")
