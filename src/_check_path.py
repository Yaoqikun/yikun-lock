import os, sys, inspect

print('=== 检查导入来源 ===')
print(f'frozen: {getattr(sys, "frozen", False)}')
print(f'sys.path[0]: {sys.path[0]}')

# 检查当前文件位置
current_file = inspect.getfile(inspect.currentframe())
print(f'当前文件: {current_file}')

# 检查两个可能的位置
locations = [
    os.path.join(sys.path[0], 'src'),
    os.path.join(os.path.dirname(sys.path[0]), '_internal', 'src'),
]
for loc in locations:
    print(f'{loc}: exists={os.path.exists(loc)}')