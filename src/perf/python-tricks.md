# Что выжать из самого Python

> Опирается на главу [«Почему Python не очень быстрый»](../dev/python/optimization.md): прежде чем ускорять, надо измерить, а прежде чем измерять, надо понимать, откуда берётся медлительность.

Компиляторы и векторизация будут в следующей главе, а здесь речь о том, что не требует ничего, кроме самого языка. Выигрыш тут обычно скромнее, зато и цена нулевая: код остаётся обычным Python, который прочитает любой коллега, не посвящённый в твои ухищрения.

## Часть 1. Что оптимизировать

Оптимизация не сводится к правке кода, так как уровней, пригодных для ускорения уже написанной программы, несколько.

### 1. Общая архитектура

То, как система устроена целиком, какие данные она обрабатывает, каким способом, в каком объёме и где их хранит.

### 2. Алгоритмы и структуры данных

Выбор алгоритма и структуры данных под конкретную обработку.

### 3. Реализация (код)

То, как выбранный алгоритм записан на языке.

### 4. Оптимизации во время компиляции

То, что компилятор или JIT способен сделать за тебя с уже написанным кодом.

### 5. Оптимизации во время исполнения

То, что можно подкрутить в уже работающей программе, включая кеши, ленивые вычисления и специализацию под найденный профилировщиком горячий путь.

Дальше речь пойдёт об уровнях 3–5, что вовсе не значит, будто первые два менее важны. Как раз у них потенциал ускорения наибольший, и цена ошибки тоже, поскольку переделывать однажды выбранную архитектуру посреди работы дорого.

Оптимизировать, кстати, можно не только скорость, поскольку столь же осмысленно бороться за память, за место на диске и число обращений к нему, за сетевой трафик, за потребление энергии, но из перечисленного мы разберём только скорость и память.

И помни, что за оптимизацию всегда приходится платить.

1. Она отнимает твоё время, и нет никакой гарантии, что потраченные часы что-то дадут.
1. Система в целом станет сложнее, а код, написанный ради нескольких процентов, непонятнее.
1. Не всякая оптимизация полезна, ведь легко выиграть в скорости и крупно проиграть в памяти.

## Часть 2. Пишем хороший Python код

Займёмся третьим уровнем, самой реализацией, для чего ниже собрана дюжина советов, и каждый из них сопровождается замером, сделанным на одной машине. Выигрыш дают не все.

### Совет 1. Используй builtins

Посчитаем количество элементов в заранее созданном списке.


```python
one_million_elements = [i for i in range(1000000)]

def calc_total(elements):
    total = 0
    for item in elements:
        total += 1
    
%timeit calc_total(one_million_elements)
```

    31.6 ms ± 404 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)



```python
%timeit len(one_million_elements)
```

    43.6 ns ± 1.03 ns per loop (mean ± std. dev. of 7 runs, 10,000,000 loops each)


Пример игрушечный, но мораль общая, и если нужное уже есть в `builtins`, то почти всегда быстрее взять готовое, чем писать своё, поскольку встроенные функции, написанные на C, обходятся без цикла на уровне интерпретатора.

### Совет 2. Правильная фильтрация

Отберём из списка нечётные элементы, заодно воспользовавшись предыдущим советом и взяв встроенный `filter`.


```python
def my_filter1(elements):
    result = []
    for item in elements:
        if item % 2:
            result.append(item)
    return result
            
def my_filter2(elements):
    return list(filter(lambda x: x % 2, elements))
```


```python
%timeit my_filter1(one_million_elements)
```

    45.6 ms ± 344 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)



```python
%timeit my_filter2(one_million_elements)
```

    76.8 ms ± 780 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


Замедление объясняется накладными расходами: `filter` создаёт итератор, к каждому элементу применяется Python-функция `lambda`, а полученный итератор ещё нужно превратить в список.

Запишем то же самое выражением, создающим нужный список сразу.


```python
def my_filter3(elements):
    return [item for item in elements if item % 2]

%timeit my_filter3(one_million_elements)
```

    40.3 ms ± 1.01 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)



```python
one_million_elements_str = [str(i) for i in range(1000000)]

def str_filter1(elements):
    return [item for item in elements if item.isdigit()]

def str_filter2(elements):
    return list(filter(str.isdigit, elements))
```


```python
%timeit str_filter1(one_million_elements_str)
```

    55.3 ms ± 244 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)



```python
%timeit str_filter2(one_million_elements_str)
```

    49.8 ms ± 166 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


Итак, `builtins` и генераторы не ускоряют код сами по себе, ведь стоило заменить `lambda` на готовый метод `str.isdigit`, написанный на C, и картина стала обратной — `filter` выиграл. Проверяй свой случай замером.

### Совет 3. Правильная проверка вхождений

> Разница между `in` по списку и по множеству разобрана в главе [«Сложность операций с коллекциями»](../dev/python/o-notation.md). Здесь добавим то, чего там нет: цену построения множества и расход памяти.

Напишем код, проверяющий наличие элемента.


```python
def check_in1(elements, number):
    for item in elements:
        if item == number:
            return True
    return False

%timeit check_in1(one_million_elements, 500000)
```

    9.02 ms ± 34.1 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit 500000 in one_million_elements
```

    5.65 ms ± 21.4 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Но время поиска зависит от места, где лежит элемент: список просматривается подряд, пока не найдётся заданное значение.


```python
%timeit 42 in one_million_elements
```

    492 ns ± 2.24 ns per loop (mean ± std. dev. of 7 runs, 1,000,000 loops each)


Для такой задачи в Python есть множество `set`, проверка вхождения в которое идёт по хешу, то есть за \\(O(1)\\) вместо \\(O(n)\\).


```python
one_million_elements_set = set(one_million_elements)
%timeit 500000 in one_million_elements_set
```

    37.3 ns ± 0.345 ns per loop (mean ± std. dev. of 7 runs, 10,000,000 loops each)



```python
%timeit 42 in one_million_elements_set
```

    23.5 ns ± 0.223 ns per loop (mean ± std. dev. of 7 runs, 10,000,000 loops each)


Само собой, за это приходится платить временем, потраченным на построение множества.


```python
%timeit set(one_million_elements)
```

    46.7 ms ± 358 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


И памятью, поскольку множество держит хеш-таблицу с запасом, а не уложенные подряд элементы. Строить его ради одной проверки бессмысленно, а ради миллиона обязательно.

### Совет 4. Сортировка


```python
import random

data = [random.random() for _ in range(1_000_000)]
%timeit sorted(data)
```

    120.7 ms ± 3.1 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)



```python
%timeit (lambda a: a.sort())(data[:])
```

    108.5 ms ± 2.8 ms per loop (mean ± std. dev. of 7 runs, 10 loops each)


Данные здесь взяты случайные, и это принципиально. На уже отсортированном списке Timsort вырождается в один линейный проход, оба замера падают примерно до 13 мс, и разницы между ними не остаётся вовсе. Копируют, кстати, оба: `sorted` делает копию внутри себя, а второму варианту её делает срез, и стоит она всего около 2 мс. На случайных данных `sort` всё же выходит вперёд на десяток процентов, так что, если исходный порядок не нужен, пользуйся методом, работающим на месте.

### Совет 5. Условия if

Условие в `if` можно записать по-разному, и выбор записи влияет на время, уходящее в цикле.


```python
count = 100000

def check_false1(flag):
    for i in range(count):
        if flag == False:
            pass
    
def check_false2(flag):
    for i in range(count):
        if flag is False:
            pass

def check_false3(flag):
    for i in range(count):
        if not flag:
            pass
```

И работают эти варианты разное время.


```python
%timeit check_false1(True)
```

    3.7 ms ± 31.6 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_false2(True)
```

    2.6 ms ± 9.39 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_false3(True)
```

    2.14 ms ± 13.9 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Попробуй угадать, какая из трёх проверок на пустоту быстрее.
1. `if len(elements) == 0:`
2. `if elements == []:`
3. `if not elements:`


```python
def check_empty1(elements):
    for i in range(count):
        if len(elements) == 0:
            pass
    
def check_empty2(elements):
    for i in range(count):
        if elements == []:
            pass

def check_empty2_new(elements):
    for i in range(count):
        if elements == list():
            pass
        
def check_empty3(elements):
    for i in range(count):
        if not elements:
            pass
```


```python
%timeit check_empty1(one_million_elements)
```

    5.98 ms ± 38.9 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_empty2(one_million_elements)
```

    5.54 ms ± 53.1 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_empty2_new(one_million_elements)
```

    8.73 ms ± 33.4 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_empty3(one_million_elements)
```

    2.97 ms ± 43 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Самым быстрым здесь оказался заодно и самый идиоматичный вариант `if not elements`, рекомендованный любым руководством по стилю. Так бывает нечасто, но приятно.

### Совет 6. Спрашивать разрешения или обрабатывать последствия

Предположим, код должен работать и с объектами, у которых нужный атрибут есть, и с теми, у которых его нет.


```python
class Foo:
    attr1 = 'hello'
    
foo = Foo()
```


```python
def check_attr1(obj):
    for i in range(count):
        if hasattr(obj, 'attr1'):
            obj.attr1
            
def check_attr2(obj):
    for i in range(count):
        try:
            obj.attr1
        except AttributeError:
            pass
```

Сравним оба описанных способа замером.


```python
%timeit check_attr1(foo)
```

    8.42 ms ± 70.3 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_attr2(foo)
```

    4.63 ms ± 29.5 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Разница станет ещё больше, если атрибутов, требующих проверки, несколько.

Подвох обнаружится дальше.

Предположим теперь, что у объектов, которые попадают в функцию, нужного атрибута в основном нет.


```python
class Bar:
    pass

bar = Bar()
```


```python
%timeit check_attr1(bar)
```

    5.91 ms ± 74.3 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit check_attr2(bar)
```

    59.5 ms ± 897 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


Мораль проста, и разница тут в том, что исключение, брошенное один раз, обходится дёшево, а миллион раз подряд — дорого. Выбирай между `hasattr` и `try/except` по тому, какая ситуация встречается чаще.

### Совет 7. Особенности определения словаря и списка

Словарь и список можно объявить двумя способами, дающими одинаковый результат.


```python
def create_list1():
    for i in range(count):
        a = []

def create_list2():
    for i in range(count):
        a = list()
        
def create_dict1():
    for i in range(count):
        a = {}

def create_dict2():
    for i in range(count):
        a = dict()
```

При этом способы через `[]` и `{}` быстрее `list()` и `dict()` соответственно.


```python
%timeit create_list1()
```

    4.12 ms ± 127 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit create_list2()
```

    7.16 ms ± 164 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit create_dict1()
```

    4.04 ms ± 93.6 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit create_dict2()
```

    7.82 ms ± 115 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


Разница берётся из обращения к имени, поскольку интерпретатору нужно выяснить, на что указывает `list`, тогда как литерал компилируется в одну инструкцию. Разберём байт-код модулем `dis` и убедимся, что порождённый код и правда разный.


```python
import dis

dis.dis("[]")
```

      0           0 RESUME                   0
    
      1           2 BUILD_LIST               0
                  4 RETURN_VALUE



```python
import dis

dis.dis("list()")
```

      0           0 RESUME                   0
    
      1           2 PUSH_NULL
                  4 LOAD_NAME                0 (list)
                  6 CALL                     0
                 14 RETURN_VALUE


### Совет 8. Вызов функции

Если функцию можно не вызывать, лучше не вызывать, поскольку на каждый вызов создаётся кадр стека, и потраченное на него время заметно.


```python
def square(num):
    return num ** 2
```


```python
%timeit [square(num) for num in range(10000)]
```

    1.05 ms ± 6.03 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)



```python
%timeit [num ** 2 for num in range(10000)]
```

    694 μs ± 6.45 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


### Совет 9. Избегай активной работы с глобальными переменными


```python
count = 100000

some_global = 0
def work_with_global():
    global some_global
    for i in range(count):
        some_global += 1
        
def work_with_local():
    some_local = 0
    for i in range(count):
        some_local += 1
```


```python
%timeit work_with_global()
```

    6.98 ms ± 56.6 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
%timeit work_with_local()
```

    4.16 ms ± 41.8 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)



```python
some_global = 0
def work_with_global_optimized():
    global some_global
    some_local = some_global
    for i in range(count):
        some_local += 1
    some_global = some_local
```


```python
%timeit work_with_global_optimized()
```

    4.14 ms ± 75.4 μs per loop (mean ± std. dev. of 7 runs, 100 loops each)


### Совет 10. Для математики используй соответствующие библиотеки

Не пиши численные расчёты циклами на Python, поскольку для этого есть библиотеки на C и Фортране, дающие разницу в десятки раз.


```python
def list_slow():
    a = range(10000)
    return [i ** 2 for i in a]

%timeit list_slow()
```

    658 μs ± 4.81 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)



```python
import numpy as np

def list_fast():
    a = np.arange(10000)
    return a ** 2

%timeit list_fast()
```

    10.4 μs ± 32.3 ns per loop (mean ± std. dev. of 7 runs, 100,000 loops each)


### Опасная зона

Дальше идут уловки, ухудшающие читаемость кода ради нескольких процентов, так что применяй их, только если профилировщик показал, что эти проценты действительно нужны.

### Совет 11. Множественное присваивание


```python
def create_variables1():
    for i in range(10000):
        a = 0
        b = 1
        c = 2
        d = 3
        e = 4
        f = 5
        g = 6
        h = 7
        i = 8
        j = 9
        
def create_variables2():
    for i in range(10000):
        a, b, c, d, e, f, g, h, i, j = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9
```


```python
%timeit create_variables1()
```

    616 μs ± 5.26 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)



```python
%timeit create_variables2()
```

    503 μs ± 8.69 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


Объявление в одну строку и правда быстрее, поскольку распаковка кортежа обходится дешевле десяти отдельных присваиваний. Но читать полученную строку невозможно, и выигрыш в сотню микросекунд того не стоит.

### Совет 12. Поиск функций и атрибутов

Поиск атрибута в Python обходится не бесплатно, так как за ним стоит `__getattribute__`, а если тот ничего не нашёл, то и `__getattr__`. Напрашивается очевидное решение, состоящее в том, чтобы найти атрибут один раз и сохранить в локальную переменную, не разыскивая его заново на каждой итерации.


```python
def squares1(elements):
    result = []
    for item in elements:
        result.append(item)

def squares2(elements):
    result = []
    append = result.append
    for item in elements:
        append(item)
```


```python
%timeit squares1(one_million_elements)
```

    24.6 ms ± 255 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)



```python
%timeit squares2(one_million_elements)
```

    29 ms ± 367 μs per loop (mean ± std. dev. of 7 runs, 10 loops each)


И вот результат, в котором совет, годами кочующий по подборкам об оптимизации, проигрывает. Начиная с версии 3.11 CPython специализирует вызов метода прямо в байт-коде, и обычный `result.append(item)` оказывается быстрее заранее сохранённой ссылки.

Проверяй такие рекомендации замером, проведённым на своей версии интерпретатора.

### Прочее

За пределами CPython тоже кое-что происходит, и внимания заслуживают три проекта, решающих ту же задачу иначе.

1. [nimpy](https://github.com/yglukhov/nimpy) позволяет вызывать функции на языке Nim из Python.
2. [Pythran](https://pythran.readthedocs.io/en/latest/) предлагает ещё один подход к компиляции Python-кода.
3. [Pyston](https://github.com/pyston/pyston) представляет собой альтернативный интерпретатор, снабжённый JIT-компилятором.

## Оптимизируем память

Скорость не единственный дефицитный ресурс, и расчёт, не помещающийся в оперативную память, не спасёт никакая векторизация. Он просто не запустится.

### Замеряем память

Замерять память в Python неожиданно трудно, и первый же способ, подсказанный документацией, обманет.


```python
import sys

print(sys.getsizeof([i for i in range(1000000)]))
print(sys.getsizeof([i for i in range(100000)]))
```

    8448728
    800984


Кажется, всё работает как надо. Однако к полученным числам стоит присмотреться.


```python
class SomeClass:
    def __init__(self, i):
        self.i = i
        self.j = i * 2
        
sys.getsizeof([SomeClass(i) for i in range(1000000)])
```




    8448728



Список объектов `SomeClass` занимает столько же, сколько список целых чисел. Загадки тут нет, поскольку `sys.getsizeof` меряет размер самого списка, то есть массива указателей, а не то, на что эти указатели ведут, и надёжно работает только для простых типов и встроенных структур, размещённых в непрерывном куске памяти.

Остаётся взять профилировщик памяти.


```python
%load_ext memory_profiler
%memit
```

    peak memory: 625.96 MiB, increment: 0.00 MiB


Данный подход тоже не идеален, поскольку смотрит на потребление памяти процессом в отдельные моменты времени, из-за чего учитывает не всё, а полученные результаты заметно плавают от запуска к запуску.


```python
%memit [n for n in range(10000000)]
```

    peak memory: 1007.02 MiB, increment: 377.12 MiB



```python
%memit [n for n in range(1000000)]
```

    peak memory: 632.71 MiB, increment: 0.07 MiB


### Утечки памяти в Python

> Подсчёт ссылок, циклические ссылки и поколенческий сборщик разбирались в главе [«Объекты и память»](../dev/python/objects.md); там же и ловушка с изменяемым аргументом по умолчанию. Здесь речь о том, что утекает в долго живущей программе.

Всё зависит от того, что считать утечкой, поскольку в смысле C++ утечек почти нет. За освобождением следит сборщик мусора, и потерять память по-настоящему можно разве что напортив со счётчиком ссылок в расширении, написанном на C. Подробнее об этом рассказано в [разборе устройства сборщика](https://rushter.com/blog/python-garbage-collector/).

А вот долгоживущие бесполезные объекты получить легко, и на практике утечкой обычно называют как раз их. Классических способов три, и первый из них состоит в изменяемом аргументе по умолчанию, второй — в забытой переменной, живущей всё время работы длинной функции, а третий — в заведённом на атрибуте класса кеше, из которого ничего никогда не удаляется.


```python
def mutable_argument(arr=[]):
    arr.append(42)
    return arr
```


```python
def unused_variable_in_long_process(arg1, arg2, arg3, unused_variable):
    pass
```


```python
class ClassCaching:
    cache = {}                      # общий на весь класс, а не на экземпляр

    def calc(self, arg):
        result = self.cache.get(arg)
        if result is not None:
            return result
        result = do_calc(arg)
        self.cache[arg] = result    # растёт вечно: удалять отсюда некому
        return result
```

Отдельная история со старыми версиями Python (2.7 и всё до 3.4), где сборщик не умел разбирать циклические ссылки между объектами с `__del__`, из-за чего образованные ими циклы жили до конца работы программы.

### Array

Теперь о том, как памяти тратить меньше, для чего годится модуль `array`, хранящий числа примитивных типов подряд, без отдельного объекта на каждый элемент.


```python
import array

%memit array.array('q', range(10000000))
```

    peak memory: 702.93 MiB, increment: 70.22 MiB


[Полный список кодов типов](https://docs.python.org/3/library/array.html) приведён в документации.

### np.array

`np.array` устроен так же, с фиксированным типом и уложенными подряд элементами, и памяти занимает существенно меньше стандартного списка. Вдобавок, в отличие от `array`, он умеет считать.


```python
np.arange(10000000).nbytes / 2**20
```

    76.29

Здесь `%memit` не годится, и на этом стоит остановиться, поскольку он меряет
прирост потребления процессом, а интерпретатор с аллокатором держат уже освобождённые
страницы про запас и охотно кладут в них вновь созданный массив. В таком случае `%memit`
покажет `increment: 0.00 MiB` для восьмидесяти мегабайт данных, и это будет не
экономия, а несостоявшееся измерение. У NumPy размер известен точно и без
всяких замеров, поскольку `nbytes` возвращает `len * itemsize`.


### tuple vs list

Кортеж чуть компактнее списка, поскольку ему не нужен запас под рост, оставляемый списком на случай дальнейшего добавления элементов. Разница невелика, зато хорошо видно, во что обходится списковое включение, создающее список с запасом места под будущие `append`.


```python
sys.getsizeof([i for i in one_million_elements])
```




    8448728




```python
sys.getsizeof(tuple(one_million_elements))
```




    8000040




```python
sys.getsizeof(list(one_million_elements))
```




    8000056



### Slots

Атрибут `__slots__` отменяет у экземпляров словарь `__dict__` и раскладывает объявленные поля по фиксированным ячейкам, чем экономит память.


```python
class SomeClass:
    def __init__(self, i):
        self.a = i
        self.b = 2 * i
        self.c = 3 * i
        self.d = 4 * i
        self.e = 5 * i
```


```python
%memit [SomeClass(i) for i in range(1000000)]
```

    peak memory: 880.38 MiB, increment: 247.62 MiB



```python
class SomeClassSlots:
    __slots__ = ('a', 'b', 'c', 'd', 'e',)
    def __init__(self, i):
        self.a = i
        self.b = 2 * i
        self.c = 3 * i
        self.d = 4 * i
        self.e = 5 * i
                
%memit [SomeClassSlots(i) for i in range(1000000)]
```

    peak memory: 853.01 MiB, increment: 217.66 MiB


Обычно `__slots__` заодно ускоряет и обращение к атрибуту. Обычно, но не всегда.


```python
d1 = SomeClass(0)
d2 = SomeClassSlots(0)

def attr_work(obj):
    count = 0
    for i in range(10000):
        count += obj.a + obj.b + obj.c + obj.d + obj.e
```


```python
%timeit attr_work(d1)
```

    824 μs ± 20.2 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)



```python
%timeit attr_work(d2)
```

    845 μs ± 7.76 μs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)


Здесь разница ушла в шум, поскольку современный CPython кеширует поиск атрибута и в обычном `__dict__`. Ещё один повод не верить советам, не подкреплённым замером.

А вот с наследованием со `__slots__` неудобно, ведь указывать его приходится в каждом классе иерархии, иначе `__dict__` вернётся и вся экономия пропадёт.

### bitarray

Пакет [bitarray](https://github.com/ilanschnell/bitarray) хранит булевы значения по одному биту на элемент, а не по указателю на объект, из-за чего на десяти миллионах флагов разница уже заметна.


```python
import bitarray.util as bu

bu.zeros(10000000).nbytes / 2**20
```

    1.19



```python
%memit [False for i in range(10000000)]
```

    peak memory: 701.93 MiB, increment: 67.81 MiB


Платой становится время, поскольку упакованный флаг надо ещё вынуть из байта.

### `range` и вычисление вместо хранения

Иногда последовательность вообще не нужно хранить, и `range`, не держащий элементы в памяти, вычисляет нужный по индексу, а `len` тоже считает по формуле.


```python
a = range(1, 100000, 3)
print(a[10])
print(len(a))
```

    31
    33333


Тот же ход, вычисление вместо хранения, работает и для более сложных последовательностей, а промежуточным вариантом служит расчёт, сохраняющий в кеше то, что запрашивают чаще всего.

## Другой полезный инструментарий

Если дело дошло до серьёзных разбирательств с памятью, пригодятся ещё два инструмента, работающих уже с живой кучей.

1. [objgraph](https://github.com/mgedmin/objgraph) рисует граф ссылок и помогает понять, кто держит объект живым.
2. [guppy3](https://github.com/zhuyifei1999/guppy3) собирает подробную статистику по куче.


## Резюме

* Оптимизировать имеет смысл только измеренное, поскольку интуиция о том, где программа проводит время, врёт систематически, из-за чего сначала берётся профилировщик, а уже потом правки.
* Оптимизация всегда чего-то стоит, отнимая время разработки, читаемость кода, иногда и корректность, поэтому, прежде чем ускорять, стоит убедиться, что медленная работа действительно составляет проблему.
* Самый дешёвый выигрыш обычно даёт не микрооптимизация, а смена структуры данных или алгоритма, когда замена списка на множество в проверке вхождения меняет \\(O(n)\\) на \\(O(1)\\).
* Для памяти работают свои средства, такие как `__slots__`, `array` и генераторы вместо списков, не ускоряющие код, зато позволяющие обработать данные, которые иначе не поместились бы.
* И главное правило — **сначала правильно, потом быстро**. Ускоренный неверный расчёт остаётся неверным.
