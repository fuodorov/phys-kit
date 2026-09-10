# Основы языка

> Беглый справочник для тех, кто Python не знает вовсе. Полностью тема разобрана в основных главах книги; в печатное издание приложение не вошло.


Python представляет собой высокоуровневый мультипарадигменный язык программирования с динамической типизацией, о коде на котором часто говорят, что он почти как псевдокод: очень мощные идеи выражаются буквально в нескольких строках и при этом легко читаются.

Рекомендуем прочитать [PEP 8](https://www.python.org/dev/peps/pep-0008/).

## Версии Python и Дзен Python

Сейчас поддерживаются версии Python 3.X, тогда как поддержка Python 2.7 прекратилась в 2020 году, а весь код в книге рассчитан на Python 3.10 и новее.

Проверить свою версию Python можно в командной строке, запустив python --version.


```python
!python --version
```

    Python 3.7.4



```python
import this
```

    The Zen of Python, by Tim Peters
    
    Beautiful is better than ugly.
    Explicit is better than implicit.
    Simple is better than complex.
    Complex is better than complicated.
    Flat is better than nested.
    Sparse is better than dense.
    Readability counts.
    Special cases aren't special enough to break the rules.
    Although practicality beats purity.
    Errors should never pass silently.
    Unless explicitly silenced.
    In the face of ambiguity, refuse the temptation to guess.
    There should be one-- and preferably only one --obvious way to do it.
    Although that way may not be obvious at first unless you're Dutch.
    Now is better than never.
    Although never is often better than *right* now.
    If the implementation is hard to explain, it's a bad idea.
    If the implementation is easy to explain, it may be a good idea.
    Namespaces are one honking great idea -- let's do more of those!


## Основные типы данных

### Числа

Целые и вещественные числа работают так, как ты и ожидаешь по опыту других языков.


```python
x = 3
print(x, type(x))
```

    3 <class 'int'>



```python
print(x + 1)   # Сложение;
print(x - 1)   # Вычитание;
print(x * 2)   # Умножение;
print(x ** 2)  # Возведение в степень;
```

    4
    2
    6
    9



```python
x += 1
print(x)  # Выведет "4"
x *= 2
print(x)  # Выведет "8"
```

    4
    8



```python
y = 2.5
print(type(y)) # Выведет "<class 'float'>"
print(y, y + 1, y * 2, y ** 2) # Выведет "2.5 3.5 5.0 6.25"
```

    <class 'float'>
    2.5 3.5 5.0 6.25


В отличие от многих языков, в Python нет унарных операторов инкремента (x++) и декремента (x--). Зато целые здесь неограниченной точности — отдельного типа для длинных целых, как в Python 2, нет, `int` растёт, пока хватает памяти, — и есть встроенный тип комплексных чисел, все подробности о которых найдёшь в [документации](https://docs.python.org/3/library/stdtypes.html#numeric-types-int-float-complex).

### Булевы значения

В Python реализованы все привычные операторы булевой логики, но вместо символов (`&&`, `||` и т.д.) используются английские слова.


```python
T, F = True, False
print(type(T)) # Выведет "<class 'bool'>"
```

    <class 'bool'>


А теперь посмотрим на операции.


```python
print(T and F) # Логическое И;
print(T or F)  # Логическое ИЛИ;
print(not T)   # Логическое НЕ;
print(T != F)  # Логическое исключающее ИЛИ;
```

    False
    True
    False
    True


### Строки


```python
hello = 'hello'   # Строковые литералы можно записывать в одинарных кавычках
world = "world"   # или в двойных — это не имеет значения.
print(hello, len(hello))
```

    hello 5



```python
hw = hello + ' ' + world  # Конкатенация строк
print(hw)  # выведет "hello world"
```

    hello world



```python
hw12 = '%s %s %d' % (hello, world, 12)  # форматирование строки в стиле sprintf
print(hw12)  # выведет "hello world 12"
```

    hello world 12


Так строки собирали до версии 3.6, и в чужом коде ты этот стиль ещё не раз встретишь, но новое пишут f-строками, которые с тех пор и стали основным способом: перед кавычками ставится буква `f`, а всё, что стоит внутри строки в фигурных скобках, вычисляется и подставляется на место.


```python
n = 12
print(f'{hello} {world} {n}')  # выведет "hello world 12"
```

    hello world 12


У строковых объектов есть куча полезных методов.


```python
s = "hello"
print(s.capitalize())  # Первая буква становится заглавной; выведет "Hello"
print(s.upper())       # Перевод строки в верхний регистр; выведет "HELLO"
print(s.rjust(7))      # Выравнивание по правому краю с дополнением пробелами; выведет "  hello"
print(s.center(7))     # Центрирование строки с дополнением пробелами; выведет " hello "
print(s.replace('l', '(ell)'))  # Замена всех вхождений одной подстроки на другую;
                               # выведет "he(ell)(ell)o"
print('  world '.strip())  # Удаление пробелов в начале и в конце; выведет "world"
```

    Hello
    HELLO
      hello
     hello 
    he(ell)(ell)o
    world


Список всех строковых методов найдёшь в [документации](https://docs.python.org/3/library/stdtypes.html#string-methods).

## Контейнеры

К встроенным контейнерным типам Python относятся списки, словари, множества и кортежи.

### Списки

Список служит аналогом массива в Python, но его размер можно менять, а элементы могут быть разных типов.


```python
xs = [3, 1, 2]   # Создаём список
print(xs, xs[2])
print(xs[-1])     # Отрицательные индексы отсчитываются с конца списка; выведет "2"
```

    [3, 1, 2] 2
    2



```python
xs[2] = 'foo'    # Списки могут содержать элементы разных типов
print(xs)
```

    [3, 1, 'foo']



```python
xs.append('bar') # Добавляем новый элемент в конец списка
print(xs)  
```

    [3, 1, 'foo', 'bar']



```python
x = xs.pop()     # Удаляем и возвращаем последний элемент списка
print(x, xs) 
```

    bar [3, 1, 'foo']


Как обычно, все кровавые подробности о списках найдёшь в [документации](https://docs.python.org/3/tutorial/datastructures.html#more-on-lists).

### Срезы

Помимо доступа к элементам списка по одному, в Python есть лаконичный синтаксис для работы с подсписками, называемый срезами (slicing).


```python
nums = list(range(5))  # range не создаёт список, поэтому оборачиваем в list
print(nums)         # Выведет "[0, 1, 2, 3, 4]"
print(nums[2:4])    # Срез с индекса 2 до 4 (не включая); выведет "[2, 3]"
print(nums[2:])     # Срез с индекса 2 до конца; выведет "[2, 3, 4]"
print(nums[:2])     # Срез с начала до индекса 2 (не включая); выведет "[0, 1]"
print(nums[:])      # Срез всего списка; выведет "[0, 1, 2, 3, 4]"
print(nums[:-1])    # Индексы среза могут быть отрицательными; выведет "[0, 1, 2, 3]"
```

    [0, 1, 2, 3, 4]
    [2, 3]
    [2, 3, 4]
    [0, 1]
    [0, 1, 2, 3, 4]
    [0, 1, 2, 3]


### Циклы

Пройтись циклом по элементам списка можно так.


```python
animals = ['cat', 'dog', 'monkey']
for animal in animals:
    print(animal)
```

    cat
    dog
    monkey


Если внутри тела цикла тебе нужен ещё и индекс каждого элемента, используй встроенную функцию `enumerate`.


```python
animals = ['cat', 'dog', 'monkey']
for idx, animal in enumerate(animals):
    print(f'#{idx + 1}: {animal}')
```

    #1: cat
    #2: dog
    #3: monkey


### Списковые включения (list comprehensions)

При программировании нам часто нужно преобразовать данные одного вида в другой, и в качестве простого примера рассмотрим код, вычисляющий квадраты чисел.


```python
nums = [0, 1, 2, 3, 4]
squares = []
for x in nums:
    squares.append(x ** 2)
print(squares)
```

    [0, 1, 4, 9, 16]


Этот код можно записать проще с помощью спискового включения (list comprehension).


```python
nums = [0, 1, 2, 3, 4]
squares = [x ** 2 for x in nums]
print(squares)
```

    [0, 1, 4, 9, 16]


List comprehensions могут содержать и условия.


```python
nums = [0, 1, 2, 3, 4]
even_squares = [x ** 2 for x in nums if x % 2 == 0]
print(even_squares)
```

    [0, 4, 16]


### Словари

Словарь хранит пары (ключ, значение), примерно как `Map` в Java или объект в Javascript, а использовать его можно так.


```python
d = {'cat': 'cute', 'dog': 'furry'}  # Создаём новый словарь с данными
print(d['cat'])       # Получаем запись из словаря; выведет "cute"
print('cat' in d)     # Проверяем, есть ли в словаре ключ; выведет "True"
```

    cute
    True



```python
d['fish'] = 'wet'    # Добавляем запись в словарь
print(d['fish'])      # Выведет "wet"
```

    wet



```python
print(d.get('monkey', 'N/A'))  # Получаем элемент со значением по умолчанию; выведет "N/A"
print(d.get('fish', 'N/A'))   # Получаем элемент со значением по умолчанию; выведет "wet"
```

    N/A
    wet



```python
del d['fish']        # Удаляем элемент из словаря
print(d.get('fish', 'N/A')) # ключа "fish" больше нет; выведет "N/A"
```

    N/A


Всё, что нужно знать о словарях, найдёшь в [документации](https://docs.python.org/3/library/stdtypes.html#dict), а итерироваться по ключам словаря легко.


```python
d = {'person': 2, 'cat': 4, 'spider': 8}
for animal in d:
    legs = d[animal]
    print(f'A {animal} has {legs} legs')
```

    A person has 2 legs
    A cat has 4 legs
    A spider has 8 legs


Словарные включения (dictionary comprehensions) похожи на списковые, но позволяют легко строить словари.


```python
nums = [0, 1, 2, 3, 4]
even_num_to_square = {x: x ** 2 for x in nums if x % 2 == 0}
print(even_num_to_square)
```

    {0: 0, 2: 4, 4: 16}


### Множества

Множеством называют неупорядоченную коллекцию различных элементов, что удобнее всего разобрать на простом примере.


```python
animals = {'cat', 'dog'}
print('cat' in animals)   # Проверяем, есть ли элемент в множестве; выведет "True"
print('fish' in animals)  # выведет "False"
```

    True
    False



```python
animals.add('fish')      # Добавляем элемент в множество
print('fish' in animals)
print(len(animals))       # Число элементов в множестве;
```

    True
    3



```python
animals.add('cat')       # Добавление элемента, который уже есть в множестве, ничего не делает
print(len(animals))       
animals.remove('cat')    # Удаляем элемент из множества
print(len(animals))       
```

    3
    2


_Циклы_. Итерация по множеству синтаксически ничем не отличается от итерации по списку; но так как множества неупорядочены, нельзя строить предположения о том, в каком порядке ты обойдёшь их элементы.


```python
animals = {'cat', 'dog', 'fish'}
for idx, animal in enumerate(animals):
    print(f'#{idx + 1}: {animal}')
# Порядок зависит от хеш-сида процесса и от запуска к запуску меняется
```

Один из возможных порядков:

    #1: fish
    #2: dog
    #3: cat


Множественные включения: как и списки со словарями, множества легко строить с помощью set comprehensions.


```python
from math import sqrt
print({int(sqrt(x)) for x in range(30)})
```

    {0, 1, 2, 3, 4, 5}


### Кортежи

Кортеж представляет собой (неизменяемый) упорядоченный список значений, во многом похожий на обычный список, а одно из важнейших отличий состоит в том, что кортежи можно использовать как ключи в словарях и как элементы множеств, а списки нельзя, что и показывает тривиальный пример ниже.


```python
d = {(x, x + 1): x for x in range(10)}  # Создаём словарь с ключами-кортежами
t = (5, 6)       # Создаём кортеж
print(type(t))
print(d[t])       
print(d[(1, 2)])
```

    <class 'tuple'>
    5
    1


## Функции

Функции в Python определяются с помощью ключевого слова `def`.


```python
def sign(x: float) -> str:
    '''Function sign''' # строка документации
    
    if x > 0:
        return 'positive'
    elif x < 0:
        return 'negative'
    else:
        return 'zero'

for x in [-1, 0, 1]:
    print(sign(x))
```

    negative
    zero
    positive



```python
help(sign)
```

    Help on function sign in module __main__:
    
    sign(x: float) -> str
        Function sign
    


Мы часто будем определять функции с необязательными именованными аргументами, например так.


```python
def hello(name: str, loud: bool=False) -> None:
    '''Function hello
    
    If loud is True, 
    then the name is printed in capital letters.
    '''
    
    if loud:
        print(f'HELLO, {name.upper()}')
    else:
        print(f'Hello, {name}!')

hello('Bob')
hello('Fred', loud=True)
```

    Hello, Bob!
    HELLO, FRED



```python
help(hello)
```

    Help on function hello in module __main__:
    
    hello(name: str, loud: bool = False) -> None
        Function hello
        
        If loud is True, 
        then the name is printed in capital letters.
    


## Классы

Синтаксис определения классов в Python прост.


```python
class Greeter:
    '''Class Greeter
    
    method greet:
    If loud is True, 
    then the name is printed in capital letters.
    '''

    # Конструктор
    def __init__(self, name):
        self.name = name  # Создаём переменную экземпляра

    # Метод экземпляра
    def greet(self, loud: bool=False) ->None:
        if loud:
            print(f'HELLO, {self.name.upper()}!')
        else:
            print(f'Hello, {self.name}')

g = Greeter('Fred')  # Создаём экземпляр класса Greeter
g.greet()            # Вызываем метод экземпляра; выведет "Hello, Fred"
g.greet(loud=True)   # Вызываем метод экземпляра; выведет "HELLO, FRED!"
```

    Hello, Fred
    HELLO, FRED!



```python
help(Greeter)
```

    Help on class Greeter in module __main__:
    
    class Greeter(builtins.object)
     |  Greeter(name)
     |  
     |  Class Greeter
     |  
     |  method greet:
     |  If loud is True, 
     |  then the name is printed in capital letters.
     |  
     |  Methods defined here:
     |  
     |  __init__(self, name)
     |      Initialize self.  See help(type(self)) for accurate signature.
     |  
     |  greet(self, loud: bool = False) -> None
     |      # Метод экземпляра


Этим беглый справочник по языку исчерпан. Как объекты устроены внутри и во что обходится каждая операция, разбирается в основных главах — [«Объекты и память»](./objects.md) и [«Классы»](./classes.md).
