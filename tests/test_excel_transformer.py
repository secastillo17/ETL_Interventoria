"""
Prueba unitaria del transformador de Excel de cantidades ejecutadas.
Ejecutar con: pytest tests/
"""

from pathlib import Path
import pandas as pd
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.transform.excel_transformer import transformar_excel_cantidades


def test_transformar_excel_cantidades(tmp_path):
    # Arrange: crea un Excel de prueba con una fila válida y una inválida
    df_prueba = pd.DataFrame({
        "Proyecto": ["Via Test", "Via Test"],
        "Item": ["Excavacion", "Concreto"],
        "Unidad": ["m3", "m3"],
        "Cantidad_Ejecutada": [100.0, "no_valido"],
        "Fecha_Registro": ["2026-01-01", "2026-01-02"],
    })
    archivo = tmp_path / "prueba.xlsx"
    df_prueba.to_excel(archivo, index=False)

    # Act
    resultado = transformar_excel_cantidades(archivo)

    # Assert
    assert resultado.filas_validas == 1
    assert resultado.filas_descartadas == 1
    assert len(resultado.errores) == 1
    assert resultado.dataframe.iloc[0]["proyecto"] == "Via Test"
