#!/usr/bin/env python
# coding: utf-8

# In[15]:


import pandas as pd
import numpy as np

# 3 index (lignes)
index = [1, 10, 15]

du = pd.DataFrame(
    index=index,
    columns= [
    'kWh_Solar',
    'GE',
    'G1',
    'G2',
    'G3',
    'EVUGSCH',
    'EVUGCH',
    'RestU',
    'EIG' 
]
)
du['kWh_Solar'] = [66462,63539,61958]
du['GE']        = [23492,22610,22150]
du['G1']        = [2757,2638,2573]
du['G2']        = [661,610,584]
du['G3']        = [779,721,691]
du['EVUGSCH']   = [1563,1596,1616]
du['EVUGECH']   = [21556,21750,21857]
du['RestU']     = [25951,24034,23027]
du['EIG']       = [17018, 16885, 16805]

# x-values (3 lignes)
x = np.array([1, 10, 15])

# Matrice pour résoudre a,b,c
A = np.vstack([x**2, x, np.ones_like(x)]).T   # matrice 3x3

# DataFrame résultat
dr = pd.DataFrame(index=["a", "b", "c"], columns=du.columns)

# Boucle sur les colonnes de dc
for col in du.columns:
    y = du[col].to_numpy(dtype=float)   # garantit un float64
    a, b, c = np.linalg.solve(A, y)
    dr.loc["a", col] = a
    dr.loc["b", col] = b
    dr.loc["c", col] = c
def y_for_x(dr, col, x):
    a = float(dr.loc["a", col])
    b = float(dr.loc["b", col])
    c = float(dr.loc["c", col])
    return a * x**2 + b * x + c


