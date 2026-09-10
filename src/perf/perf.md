# Скорость выполнения программ

Советы, собранные в предыдущей главе, упирались в потолок самого языка, и дальше мы пойдём другим путём, взяв одну задачу и разгоняя её шаг за шагом, каждый раз замеряя полученный результат.

Задачей послужит умножение матриц — операция самая обычная, встречающаяся в любом физическом расчёте, и при этом на ней видны все типичные способы оптимизации, накопленные за полвека численных методов.

Начнём с наивной реализации на чистом Python, измерим её, найдём профилировщиком узкое место, тормозящее счёт, а дальше последовательно применим четыре подхода: перестановку циклов, компиляцию через Numba, компиляцию через Cython и, наконец, готовую библиотеку, написанную за нас. Разница между первой и последней версией, забегая вперёд, составит несколько порядков.

## Класс `Matrix`

Для опытов понадобится сама матрица, описанная как список списков и снабжённая парой удобных конструкторов:


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

Вроде бы всё работает, но скорость пока неизвестна, поэтому проверь её магией `%%timeit`, описанной в главе [«Почему Python не очень быстрый»](../dev/python/optimization.md).


```python
%%timeit shape = 64, 64; X = Matrix.random(shape); Y = Matrix.random(shape)
matrix_product(X, Y)
```

    86.6 ms ± 1.52 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)


Итого умножение двух матриц 64×64 занимает 87 миллисекунд, почти десятую долю секунды, и причину такой медлительности, съедающей время на пустом месте, стоит поискать.

Определим вспомогательную функцию `bench`, генерирующую случайные матрицы указанного размера, а затем `n_iter` раз перемножающую их в цикле.


```python
def bench(shape=(64, 64), n_iter=16):
    X = Matrix.random(shape)
    Y = Matrix.random(shape)
    for iter in range(n_iter):
        matrix_product(X, Y)    
```

Попробуем присмотреться к происходящему повнимательнее с помощью `line_profiler`, описанного в той же главе про измерение.


```python
#!pip install line_profiler
```


```python
%load_ext line_profiler
%lprun -f matrix_product bench()
```

Операция `list.__getitem__`, как видно, не бесплатна, поэтому поменяем местами вложенные циклы `for` так, чтобы код делал меньше обращений по индексу.


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

Профилировщик показывает, что стало на две секунды быстрее, но этого мало: больше 30 % времени уходит на саму итерацию по индексам, не убранную из внутреннего цикла. Исправим и это.


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

Функция `matrix_product` заметно похорошела, но, кажется, это ещё не предел, поэтому попробуем ещё раз убрать лишние обращения по индексу, спрятанные в самом внутреннем цикле.


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

Со встроенными списками Python компилятор Numba работать толком не умеет, так как для машинного кода ему нужен массив известного типа, поэтому перепишем `matrix_product` через ndarray, хранящий числа одного типа подряд.


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

Посмотрим, что получилось.


```python
shape = 64, 64
X = np.random.randint(-255, 255, shape)
Y = np.random.randint(-255, 255, shape)

jit_matrix_product(X, Y)          # прогрев: здесь идёт компиляция
%timeit -n100 jit_matrix_product(X, Y)
```

    107 µs ± 1 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)

Строка прогрева, поставленная перед замером, тут не для красоты. Numba компилирует функцию при первом вызове
под конкретные типы аргументов, и на этой машине компиляция занимает около 360 мс,
в три тысячи раз дольше самого счёта. Без прогрева она попадает в измерение,
и `%timeit` выдаёт 495 мкс со среднеквадратичным отклонением 900 мкс, то есть
разброс больше среднего. Замер, испорченный попавшей в него компиляцией, узнаётся именно по такому разбросу. IPython
в таком случае сам предупреждает, что самый медленный прогон оказался в двадцать
раз дольше самого быстрого. После прогрева разброс падает до одной микросекунды.


## Настоящая задача: пространственный заряд

Умножение матриц остаётся учебным примером; посмотрим, что Numba даёт на реальной вычислительной задаче. В коде REDPIC, которому дальше отведена [отдельная глава](../examples/redpic.md), пучок представлен ансамблем макрочастиц, а самой дорогой функцией расчёта оказывается суммирование кулоновских сил, действующих между частицами. Это и есть эффект пространственного заряда, из-за которого сильноточный пучок расталкивает сам себя:

$$
\vec{F}_i = \sum_{j \ne i} \frac{\vec{r}_i - \vec{r}_j}{|\vec{r}_i - \vec{r}_j|^3}.
$$

Каждая частица взаимодействует с каждой, поэтому вычислительная сложность составляет \\(O(N^2)\\), где \\(N\\) обозначает число частиц. Никакой алгоритмической хитрости здесь нет, зато цикл, записанный в лоб, идеально ложится и на JIT-компиляцию, и на распараллеливание, поскольку слагаемые для разных \\(i\\) считаются независимо.

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

Чтобы получить параллельную версию, достаточно заменить внешний `range` на `prange`, и тогда Numba узнает, какой из вложенных циклов можно раздать по ядрам:

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

Форма записи здесь непривычная, `njit(func)` вместо `@njit` над определением, и так удобнее, когда одну и ту же функцию нужно померить в нескольких режимах, ведь исходник, написанный однажды, остаётся один, а обёрток несколько.

Результаты замера (Apple M4, 10 ядер; первый вызов каждой скомпилированной версии сделан заранее, чтобы в измерение не попало время компиляции):

          N | чистый Python |     @njit | @njit parallel | ускорение
       256 |       53.0 мс |   0.40 мс |        0.20 мс |   131x /   271x
       512 |      219.0 мс |   1.67 мс |        0.48 мс |   131x /   454x
      1024 |      865.7 мс |   6.88 мс |        1.68 мс |   126x /   514x
      2048 |     3503.4 мс |  28.19 мс |        6.69 мс |   124x /   524x
      4096 |    14076.2 мс | 114.68 мс |       24.80 мс |   123x /   567x

Из данной таблицы читаются три вещи.

Квадратичность видна прямо в числах, полученных на замере. При каждом удвоении \\(N\\) время растёт вчетверо, что и означает \\(O(N^2)\\) без всяких асимптотических рассуждений. JIT-компиляция сложность не меняет: она сокращает время в сто с лишним раз, но кривая, построенная по этим точкам, остаётся квадратичной. Ускорение констант и улучшение асимптотики относятся к разным вещам.

Дальше, один декоратор даёт больше сотни раз. Это не опечатка, потому что примерно настолько интерпретатор Python проигрывает машинному коду, порождённому компилятором, на арифметике в тесном цикле. Причём переписывать не пришлось ни строчки, и функция, украшенная одним декоратором, как была на Python, так и осталась.

А вот параллелизм добавляет ещё в 4–5 раз, но не в 10, хотя ядер как раз десять. Часть из них производительные, часть — энергоэффективные; к этому добавляются накладные расходы на раздачу работы, съедающие на маленьких \\(N\\) почти весь выигрыш, и при \\(N = 256\\) параллельная версия обгоняет последовательную лишь вдвое. Линейного масштабирования по числу ядер, обещанного в учебниках, на практике почти не бывает.

С точки зрения физики, а не программирования, важно вот что. Расчёт с 4096 макрочастицами на чистом Python занимает 14 секунд на один вызов функции, а в моделировании таких вызовов десятки тысяч, по одному на каждый шаг интегрирования. Разница между 14 секундами и 25 миллисекундами превращается в разницу между «расчёт не сходится за ночь» и «расчёт готов к обеду». Она и делает возможным численное моделирование динамики пучка, запущенное на обычном сервере, без суперкомпьютера.

## Cython

Вторым путём к машинному коду служит Cython, тот же Python, но с аннотациями типов: код, снабжённый ими, транслируется в C и компилируется. Здесь придётся поработать руками, зато и контроля больше.


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


Проблема в том, что Cython не умеет эффективно оптимизировать работу со списками, в которых могут лежать элементы разных типов, поэтому перепишем `matrix_product` с использованием *ndarray*.


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


Как же так! Стало только хуже, поскольку большая часть кода, оставленного без изменений, по-прежнему использует вызовы Python. Избавимся от них, аннотировав код типами.


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


К сожалению, аннотации типов не изменили время работы, потому что тело вложенного цикла Cython так и не смог оптимизировать. Время для фаталити: укажем тип элементов в *ndarray*.


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


Попробуем пойти дальше и отключить проверку выхода за границы массива. Проверку переполнения целых отключать не нужно, поскольку в Cython она и так выключена по умолчанию, а весь выигрыш здесь даёт `boundscheck`. Взамен ошибка, допущенная в индексе, перестанет возбуждать `IndexError` и молча полезет в чужую память, поэтому границы такого цикла надо выверять глазами.


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

А теперь то, с чего стоило начать.


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


Оператор `@` выполняет то же самое матричное умножение, что и `X.dot(Y)`, только записан короче. Под обеими записями стоит один и тот же вызов, и замеры, сделанные рядом, это подтверждают.

Приведение к `float64` в первой строке косметикой не является. `np.random.randint` возвращает `int64`, а BLAS умеет только `float32`, `float64` и комплексные типы; на целых матрицах NumPy считает своим циклом и выдаёт около 70 мкс вместо 2.7. Тип данных, выбранный на входе, здесь решает больше, чем выбор между `dot` и `@`.

Взгляни на масштаб. Наивная реализация, написанная в лоб на чистом Python, считала произведение матриц 64×64 около 0.1 секунды, NumPy справляется за единицы микросекунд, давая ускорение в десятки тысяч раз и без единой строчки на C с твоей стороны. Под капотом NumPy вызывает BLAS, вылизанную десятилетиями библиотеку линейной алгебры, использующую векторные инструкции процессора и оптимально работающую с кешем.

Отсюда главный вывод раздела: **прежде чем компилировать Python, попробуй не писать циклы вообще**. Numba и Cython нужны там, где задача принципиально не векторизуется; во всех остальных случаях правильно применённый NumPy обгонит их без всякой возни со сборкой и объявленными типами.

> **Задание.** Найди свой медленный расчёт, сними с него профиль и разгони: [«Профилирование и векторизация расчёта»](../practicum/profiling-task.md).
