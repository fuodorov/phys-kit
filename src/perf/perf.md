# Скорость выполнения программ

В настоящей главе рассматривается последовательное ускорение одной задачи, при котором результат измеряется на каждом шаге.

В качестве задачи выбрано умножение матриц — операция, встречающаяся в любом физическом расчёте, на которой видны все типичные способы оптимизации.

Начнём с наивной реализации на чистом Python, измерим её, найдём с помощью профилировщика узкое место, а затем последовательно применим четыре подхода: перестановку циклов, компиляцию через Numba, компиляцию через Cython и готовую библиотеку. Разница между первой и последней версией составит несколько порядков.

## Класс `Matrix`

Матрица описана как список списков с парой конструкторов:


```python
import random

class Matrix(list):
    @classmethod
    def zeros(cls, shape):
        n_rows, n_cols = shape
        return cls([[0] * n_cols for i in range(n_rows)])

    @classmethod
    def random(cls, shape):
        M, (n_rows, n_cols) = cls(), shape
        for i in range(n_rows):
            M.append([random.randint(-255, 255)
                      for j in range(n_cols)])
        return M

    def transpose(self):
        n_rows, n_cols = self.shape
        return self.__class__(zip(*self))

    @property
    def shape(self):
        return ((0, 0) if not self else
                (len(self), len(self[0])))
```


```python
def matrix_product(X, Y):
    """Вычисляет матричное произведение X и Y.

    >>> X = Matrix([[1], [2], [3]])
    >>> Y = Matrix([[4, 5, 6]])
    >>> matrix_product(X, Y)
    [[4, 5, 6], [8, 10, 12], [12, 15, 18]]
    >>> matrix_product(Y, X)
    [[32]]
    """
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    # верим, что с размерностями всё хорошо
    Z = Matrix.zeros((n_xrows, n_ycols))
    for i in range(n_xrows):
        for j in range(n_xcols):
            for k in range(n_ycols):
                Z[i][k] += X[i][j] * Y[j][k]
    return Z
```


```python
%doctest_mode
```

    Exception reporting mode: Plain
    Doctest mode is: ON



```python
>>> X = Matrix([[1], [2], [3]])
>>> Y = Matrix([[4, 5, 6]])
>>> matrix_product(X, Y)
[[4, 5, 6], [8, 10, 12], [12, 15, 18]]
>>> matrix_product(Y, X)

[[32]]
```




    [[32]]




```python
%doctest_mode
```

    Exception reporting mode: Context
    Doctest mode is: OFF


## Измерение времени выполнения

Реализация работает корректно; её скорость измеряется магической командой `%%timeit`, описанной в главе [«Почему Python не очень быстрый»](../dev/python/optimization.md).


```python
%%timeit shape = 64, 64; X = Matrix.random(shape); Y = Matrix.random(shape)
matrix_product(X, Y)
```

    86.6 ms ± 1.52 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)


Умножение двух матриц 64×64 занимает 87 миллисекунд, почти десятую долю секунды. Найдём причину.

Определим вспомогательную функцию `bench`, генерирующую случайные матрицы указанного размера и `n_iter` раз перемножающую их в цикле.


```python
def bench(shape=(64, 64), n_iter=16):
    X = Matrix.random(shape)
    Y = Matrix.random(shape)
    for iter in range(n_iter):
        matrix_product(X, Y)    
```

Рассмотрим происходящее подробнее с помощью `line_profiler`, описанного в той же главе.


```python
#!pip install line_profiler
```


```python
%load_ext line_profiler
%lprun -f matrix_product bench()
```

Операция `list.__getitem__` не является бесплатной, поэтому поменяем местами вложенные циклы `for`, чтобы код выполнял меньше обращений по индексу.


```python
def matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = Matrix.zeros((n_xrows, n_ycols))
    for i in range(n_xrows):
        Xi = X[i]
        for k in range(n_ycols):
            acc = 0
            for j in range(n_xcols):
                acc += Xi[j] * Y[j][k]
            Z[i][k] = acc
    return Z
```


```python
%lprun -f matrix_product bench()
```

Выполнение ускорилось на две секунды, однако более 30 % времени по-прежнему уходит на итерацию по индексам во внутреннем цикле. Устраним и этот недостаток.


```python
def matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = Matrix.zeros((n_xrows, n_ycols))
    for i in range(n_xrows):
        Xi, Zi = X[i], Z[i]
        for k in range(n_ycols):
            Zi[k] = sum(Xi[j] * Y[j][k] for j in range(n_xcols))
    return Z
```


```python
%lprun -f matrix_product bench()
```

Уберём лишние обращения по индексу и из самого внутреннего цикла.


```python
def matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = Matrix.zeros((n_xrows, n_ycols))
    Yt = Y.transpose()  # <--
    for i, (Xi, Zi) in enumerate(zip(X, Z)):
        for k, Ytk in enumerate(Yt):
            Zi[k] = sum(Xi[j] * Ytk[j] for j in range(n_xcols))
    return Z
```

## Numba

Со встроенными списками Python компилятор Numba работать не способен: для генерации машинного кода ему необходим массив известного типа. Перепишем `matrix_product` через ndarray, хранящий числа одного типа подряд.


```python
import numba
import numpy as np


@numba.jit
def jit_matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = np.zeros((n_xrows, n_ycols), dtype=X.dtype)
    for i in range(n_xrows):
        for k in range(n_ycols):
            for j in range(n_xcols):
                Z[i, k] += X[i, j] * Y[j, k]
    return Z
```

Рассмотрим полученный результат.


```python
shape = 64, 64
X = np.random.randint(-255, 255, shape)
Y = np.random.randint(-255, 255, shape)

jit_matrix_product(X, Y)          # прогрев: здесь идёт компиляция
%timeit -n100 jit_matrix_product(X, Y)
```

    107 µs ± 1 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)

Numba компилирует функцию при первом вызове
под конкретные типы аргументов, и на этой машине компиляция занимает около 360 мс,
что в три тысячи раз дольше самого счёта. Без прогрева она попадает в измерение,
и `%timeit` выдаёт 495 мкс со среднеквадратичным отклонением 900 мкс, то есть
разброс превышает среднее. По такому разбросу и распознаётся измерение, искажённое компиляцией. IPython
в таком случае предупреждает, что самый медленный прогон оказался в двадцать
раз дольше самого быстрого. После прогрева разброс снижается до одной микросекунды.


## Настоящая задача: пространственный заряд

Умножение матриц является учебным примером; рассмотрим, что Numba даёт на реальной задаче. В коде REDPIC, которому посвящена [отдельная глава](../examples/redpic.md), пучок представлен ансамблем макрочастиц, а наиболее затратной функцией расчёта является суммирование кулоновских сил между частицами. Это эффект пространственного заряда, из-за которого сильноточный пучок расталкивает сам себя:

$$
\vec{F}_i = \sum_{j \ne i} \frac{\vec{r}_i - \vec{r}_j}{|\vec{r}_i - \vec{r}_j|^3}.
$$

Каждая частица взаимодействует с каждой, поэтому сложность составляет \\(O(N^2)\\), где \\(N\\) — число частиц. Цикл, записанный напрямую, допускает и JIT-компиляцию, и распараллеливание, поскольку слагаемые для разных \\(i\\) вычисляются независимо.

```python
import numpy as np
from numba import njit, prange

def space_charge(x, y, z, Fx, Fy, Fz):
    for i in range(len(x)):
        for j in range(len(x)):
            if i != j:
                r3 = ((x[j]-x[i])**2 + (y[j]-y[i])**2 + (z[j]-z[i])**2)**1.5
                Fx[i] += (x[i]-x[j]) / r3
                Fy[i] += (y[i]-y[j]) / r3
                Fz[i] += (z[i]-z[j]) / r3
```

Для параллельной версии достаточно заменить внешний `range` на `prange`: таким образом Numba узнаёт, какой из вложенных циклов можно распределить по ядрам:

```python
def space_charge_par(x, y, z, Fx, Fy, Fz):
    for i in prange(len(x)):       # <-- единственное отличие
        for j in range(len(x)):
            if i != j:
                r3 = ((x[j]-x[i])**2 + (y[j]-y[i])**2 + (z[j]-z[i])**2)**1.5
                Fx[i] += (x[i]-x[j]) / r3
                Fy[i] += (y[i]-y[j]) / r3
                Fz[i] += (z[i]-z[j]) / r3

jit_version = njit(space_charge)                      # JIT
par_version = njit(parallel=True)(space_charge_par)   # JIT + ядра CPU
```

Запись `njit(func)` вместо `@njit` над определением удобна, когда одну функцию необходимо измерить в нескольких режимах: исходный код один, обёрток несколько.

Результаты измерения (Apple M4, 10 ядер; первый вызов каждой скомпилированной версии выполнен заранее, чтобы в измерение не попало время компиляции):

          N | чистый Python |     @njit | @njit parallel | ускорение
       256 |       53.0 мс |   0.40 мс |        0.20 мс |   131x /   271x
       512 |      219.0 мс |   1.67 мс |        0.48 мс |   131x /   454x
      1024 |      865.7 мс |   6.88 мс |        1.68 мс |   126x /   514x
      2048 |     3503.4 мс |  28.19 мс |        6.69 мс |   124x /   524x
      4096 |    14076.2 мс | 114.68 мс |       24.80 мс |   123x /   567x

Из таблицы следуют три вывода.

Квадратичность видна в числах. При каждом удвоении \\(N\\) время растёт вчетверо, что и означает \\(O(N^2)\\). JIT-компиляция сложность не меняет: она сокращает время более чем в сто раз, но кривая остаётся квадратичной. Ускорение констант и улучшение асимптотики являются разными вещами.

Один декоратор даёт ускорение более чем в сто раз: примерно настолько интерпретатор Python уступает машинному коду на арифметике в тесном цикле. Переписывать не потребовалось ни одной строки, функция как была написана на Python, так и осталась.

Параллелизм добавляет ещё в 4–5 раз, но не в 10, хотя ядер десять. Часть из них производительные, часть — энергоэффективные; к этому добавляются накладные расходы на распределение работы, поглощающие на малых \\(N\\) почти весь выигрыш: при \\(N = 256\\) параллельная версия опережает последовательную лишь вдвое. Линейного масштабирования по числу ядер на практике почти не встречается.

С точки зрения физики важно следующее. Расчёт с 4096 макрочастицами на чистом Python занимает 14 секунд на один вызов функции, а в моделировании таких вызовов десятки тысяч, по одному на каждый шаг интегрирования. Разница между 14 секундами и 25 миллисекундами — это разница между расчётом, не сходящимся за ночь, и расчётом, готовым за часы. Именно она делает возможным численное моделирование динамики пучка на обычном сервере, без суперкомпьютера.

## Cython

Второй путь к машинному коду — Cython, представляющий собой Python с аннотациями типов: код транслируется в C и компилируется. Ручной работы больше, однако и контроля больше.


```python
%load_ext cython
```


```python
%%capture
%%cython -a
import random

class Matrix(list):
    @classmethod
    def zeros(cls, shape):
        n_rows, n_cols = shape
        return cls([[0] * n_cols for i in range(n_rows)])

    @classmethod
    def random(cls, shape):
        M, (n_rows, n_cols) = cls(), shape
        for i in range(n_rows):
            M.append([random.randint(-255, 255)
                      for j in range(n_cols)])
        return M

    def transpose(self):
        n_rows, n_cols = self.shape
        return self.__class__(zip(*self))

    @property
    def shape(self):
        return ((0, 0) if not self else
                (int(len(self)), int(len(self[0]))))

    
def cy_matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = Matrix.zeros((n_xrows, n_ycols))
    Yt = Y.transpose()
    for i, Xi in enumerate(X):
        for k, Ytk in enumerate(Yt):
            Z[i][k] = sum(Xi[j] * Ytk[j] for j in range(n_xcols))
    return Z
```


```python
X = Matrix.random(shape)
Y = Matrix.random(shape)
```


```python
%timeit -n100 cy_matrix_product(X, Y)
```

    21.4 ms ± 1.36 ms per loop (mean ± std. dev. of 7 runs, 100 loops each)


Cython не способен эффективно оптимизировать работу со списками, в которых могут находиться элементы разных типов, поэтому перепишем `matrix_product` через *ndarray*.


```python
X = np.random.randint(-255, 255, size=shape)
Y = np.random.randint(-255, 255, size=shape)
```


```python
%%capture
%%cython -a
import numpy as np

def cy_matrix_product(X, Y):
    n_xrows, n_xcols = X.shape
    n_yrows, n_ycols = Y.shape
    Z = np.zeros((n_xrows, n_ycols), dtype=X.dtype)
    for i in range(n_xrows):
        for k in range(n_ycols):
            for j in range(n_xcols):
                Z[i, k] += X[i, j] * Y[j, k]
    return Z
```


```python
%timeit -n100 cy_matrix_product(X, Y)
```

    176 ms ± 4.65 ms per loop (mean ± std. dev. of 7 runs, 100 loops each)


Результат ухудшился: большая часть кода по-прежнему использует вызовы Python. Избавимся от них, аннотировав код типами.


```python
%%capture
%%cython -a
import numpy as np
cimport numpy as np

def cy_matrix_product(np.ndarray X, np.ndarray Y):
    cdef int n_xrows = X.shape[0]
    cdef int n_xcols = X.shape[1]
    cdef int n_yrows = Y.shape[0]
    cdef int n_ycols = Y.shape[1]
    cdef np.ndarray Z
    Z = np.zeros((n_xrows, n_ycols), dtype=X.dtype)
    for i in range(n_xrows):
        for k in range(n_ycols):
            for j in range(n_xcols):
                Z[i, k] += X[i, j] * Y[j, k]
    return Z
```


```python
%timeit -n100 cy_matrix_product(X, Y)
```

    173 ms ± 4 ms per loop (mean ± std. dev. of 7 runs, 100 loops each)


Аннотации типов не изменили время работы: тело вложенного цикла Cython так и не смог оптимизировать. Укажем тип элементов в *ndarray*.


```python
%%capture
%%cython -a
import numpy as np
cimport numpy as np

def cy_matrix_product(np.ndarray[np.int64_t, ndim=2] X,
                      np.ndarray[np.int64_t, ndim=2] Y):
    cdef int n_xrows = X.shape[0]
    cdef int n_xcols = X.shape[1]
    cdef int n_yrows = Y.shape[0]
    cdef int n_ycols = Y.shape[1]
    cdef np.ndarray[np.int64_t, ndim=2] Z = \
        np.zeros((n_xrows, n_ycols), dtype=np.int64)
    for i in range(n_xrows):
        for k in range(n_ycols):
            for j in range(n_xcols):
                Z[i, k] += X[i, j] * Y[j, k]
    return Z
```


```python
%timeit -n100 cy_matrix_product(X, Y)
```

    541 µs ± 5.14 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Отключим проверку выхода за границы массива. Проверку переполнения целых отключать не требуется: в Cython она и так выключена по умолчанию, а весь выигрыш даёт `boundscheck`. Взамен ошибка в индексе перестанет возбуждать `IndexError` и приведёт к обращению в чужую память без какого-либо сообщения, поэтому границы такого цикла необходимо выверять вручную.


```python
%%capture
%%cython -a
import numpy as np

cimport cython
cimport numpy as np

@cython.boundscheck(False)
def cy_matrix_product(np.ndarray[np.int64_t, ndim=2] X, 
                      np.ndarray[np.int64_t, ndim=2] Y):
    cdef int n_xrows = X.shape[0]
    cdef int n_xcols = X.shape[1]
    cdef int n_yrows = Y.shape[0]
    cdef int n_ycols = Y.shape[1]
    cdef np.ndarray[np.int64_t, ndim=2] Z = \
        np.zeros((n_xrows, n_ycols), dtype=np.int64)
    for i in range(n_xrows):        
        for k in range(n_ycols):
            for j in range(n_xcols):
                Z[i, k] += X[i, j] * Y[j, k]
    return Z
```


```python
%timeit -n100 cy_matrix_product(X, Y)
```

    226 µs ± 2.84 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)


## NumPy


```python
import numpy as np

X = np.random.randint(-255, 255, shape).astype(np.float64)
Y = np.random.randint(-255, 255, shape).astype(np.float64)
```


```python
%timeit -n100 X.dot(Y)
```

    2.7 µs ± 0.0 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit -n100 X@Y
```

    2.7 µs ± 0.0 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Оператор `@` выполняет то же матричное умножение, что и `X.dot(Y)`. За обеими записями стоит один и тот же вызов, и измерения это подтверждают.

Приведение к `float64` в первой строке является существенным. `np.random.randint` возвращает `int64`, а BLAS поддерживает только `float32`, `float64` и комплексные типы; на целых матрицах NumPy выполняет расчёт собственным циклом и выдаёт около 70 мкс вместо 2.7. Тип данных на входе определяет больше, чем выбор между `dot` и `@`.

Наивная реализация на чистом Python вычисляла произведение матриц 64×64 около 0.1 секунды, NumPy справляется за единицы микросекунд: ускорение в десятки тысяч раз без единой строки на C со стороны разработчика. Внутри NumPy вызывает BLAS, библиотеку линейной алгебры, использующую векторные инструкции процессора и оптимально работающую с кешем.

**Прежде чем компилировать Python, следует попытаться не писать циклы вообще.** Numba и Cython необходимы там, где задача не векторизуется; в остальных случаях правильно применённый NumPy опережает их без сборки и объявленных типов.
