[↩ Volver a la Unidad 3](../README.md)


# Árbol de decisión con Iris

Clasificación del dataset Iris con un árbol de decisión de scikit-learn, usando el largo y el ancho del pétalo.

- Divide los datos en 80 % entrenamiento y 20 % prueba, estratificado.
- Entrena un `DecisionTreeClassifier` con criterio Gini y profundidad máxima 2.
- Imprime las reglas del árbol con `export_text`.
- Grafica las regiones de decisión y marca los puntos del conjunto de prueba.

| Archivo | Contenido |
| --- | --- |
| [arbol_decision_iris.py](arbol_decision_iris.py) | Preparación de datos, entrenamiento, reglas y gráfica de regiones. |

## Ejecutar

```bash
pip install numpy matplotlib scikit-learn
python arbol_decision_iris.py
```
