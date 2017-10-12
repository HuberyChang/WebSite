# import asyncio, os, inspect, logging, functools
# from urllib import parse
# from aiohttp import web
# from apis import APIError
#
# # 定义一个装饰器可以把函数标记为URL处理函数
# # 装饰器不懂的，欢迎查看我总结的关于装饰器使用的文章：
# # http://kaimingwan.com/post/python/pythonzhuang-shi-qi-ying-yong
# # --------------get和post装饰器，用于增加__method__和__route__特殊属性，分别标记GET,POST方法和path
#
# def get(path):
#     '''
#     Define decorator @get('/path')
#     :param path:
#     :return:
#     '''
#     def decorator(func):
#         @functools.wraps(func)
#         def wrapper(*args, **kwargs):
#             return func(*args, **kwargs)
#         wrapper.__method__ = 'GET'
#         wrapper.__route__ = path
#         return wrapper
#     return decorator
#
# def post(path):
#     '''
#     define decorator @post('/path')
#     :param path:
#     :return:
#     '''
#     def decorator(func):
#         @functools.wraps(func)
#         def wrapper(*args, **kwargs):
#             return func(*args, **kwargs)
#         wrapper.__method__ = 'POST'
#         wrapper.__route__ = path
#         return wrapper
#     return decorator()
#
#
# # ---------------------------- 使用inspect模块中的signature方法来获取函数的参数，实现一些复用功能--
# # 关于inspect.Parameter 的  kind 类型有5种：
# # POSITIONAL_ONLY		只能是位置参数
# # POSITIONAL_OR_KEYWORD	可以是位置参数也可以是关键字参数
# # VAR_POSITIONAL			相当于是 *args
# # KEYWORD_ONLY			关键字参数且提供了key，相当于是 *,key
# # VAR_KEYWORD			相当于是 **kw
#
# def get_required_kw_args(fn):
#     # 如果url处理函数需要传入关键字参数，且默认是空得话，获取这个key
#     args = []
#     params = inspect.signature(fn).parameters
#     for name, param in params.items():
#         # param.default == inspect.Parameter.empty这一句表示参数的默认值要为空
#         if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
#             args.append(name)
#     return tuple(args)
#
#
# def get_named_kw_args(fn):
#     # 如果url处理函数需要传入关键字参数，获取这个key
#     args = []
#     params = inspect.signature(fn).parameters
#     for name, param in params.items():
#         if param.kind == inspect.Parameter.KEYWORD_ONLY:
#             return True
#
#  # 判断是否有指定命名关键字参数
# def has_named_kw_args(fn):
#     params = inspect.signature(fn).parameters
#     for name, param in params.items():
#         if param.kind == inspect.Parameter.KEYWORD_ONLY:
#             return True
#
# # 判断是否有关键字参数，VAR_KEYWORD对应**kw
# def has_var_kw_args(fn):
#     params = inspect.signature(fn).parameters
#     for name, param in params.items():
#         if param.kind == inspect.Parameter.VAR_KEYWORD:
#             return True
#
# # 判断是否存在一个参数叫做request，并且该参数要在其他普通的位置参数之后，即属于*kw或者**kw或者*或者*args之后的参数
# def has_request_arg(fn):
#     sig = inspect.signature(fn)
#     params = sig.parameters
#     found = False
#     for name, param in params.items():
#         if name == 'request':
#             found = True
#             continue
#         # 只能是位置参数POSITIONAL_ONLY
#         if found and (param.kind != inspect.Parameter.VAR_KEYWORD and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.)