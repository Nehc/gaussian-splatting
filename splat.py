import re, os
import numpy as np

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def ply_to_splat(ply_path):
    with open(ply_path, 'rb') as f:
        header = b""
        while not header.endswith(b'end_header\n'):
            header += f.readline()

        header_text = header.decode('utf-8')
        vertex_count = int(re.search(r'element vertex (\d+)', header_text).group(1))

        props = re.findall(r'property (\w+) (\w+)', header_text)
        dtype_map = {
            'float': 'f4', 'float32': 'f4',
            'uchar': 'u1', 'uint8': 'u1',
            'int': 'i4', 'int32': 'i4'
        }
        np_dtype = [(name, dtype_map[typ]) for typ, name in props]
        data = np.frombuffer(f.read(), dtype=np_dtype, count=vertex_count)

    # Сортировка
    if {'scale_0', 'scale_1', 'scale_2', 'opacity'}.issubset(data.dtype.names):
        importance = (
            np.exp(data['scale_0']) *
            np.exp(data['scale_1']) *
            np.exp(data['scale_2']) *
            sigmoid(data['opacity'])
        )
        sorted_indices = np.argsort(-importance)
        data = data[sorted_indices]

    # Вычисляем position и scale
    xyz = np.stack([data['x'], data['y'], data['z']], axis=1).astype('<f4')
    if 'scale_0' in data.dtype.names:
        sx = np.exp(data['scale_0']).astype('<f4')
        sy = np.exp(data['scale_1']).astype('<f4')
        sz = np.exp(data['scale_2']).astype('<f4')
    else:
        sx = sy = sz = np.full(len(data), 0.01, dtype='<f4')
    scale = np.stack([sx, sy, sz], axis=1)

    # Цвет
    if 'f_dc_0' in data.dtype.names:
        r = (sigmoid(data['f_dc_0']) * 255).astype('uint8')
        g = (sigmoid(data['f_dc_1']) * 255).astype('uint8')
        b = (sigmoid(data['f_dc_2']) * 255).astype('uint8')
    else:
        r, g, b = data['red'], data['green'], data['blue']

    if 'opacity' in data.dtype.names:
        a = (sigmoid(data['opacity']) * 255).astype('uint8')
    else:
        a = np.full(len(data), 255, dtype='uint8')

    rgba = np.stack([r, g, b, a], axis=1).astype('uint8')

    # Кватернионы
    if {'rot_0', 'rot_1', 'rot_2', 'rot_3'}.issubset(data.dtype.names):
        q = np.stack([data['rot_0'], data['rot_1'], data['rot_2'], data['rot_3']], axis=1)
        q_norm = np.linalg.norm(q, axis=1, keepdims=True)
        q_normalized = q / q_norm
        rot_bytes = ((q_normalized * 128) + 127).astype('uint8')
    else:
        rot_bytes = np.tile(np.array([255, 0, 0, 0], dtype='uint8'), (len(data), 1))

    # Собираем всё в итоговый массив
    result = np.concatenate([
        xyz.view('u1').reshape(len(data), -1),
        scale.view('u1').reshape(len(data), -1),
        rgba,
        rot_bytes
    ], axis=1)

    return result.tobytes()


def filter_density_centroid(ply_path, density_quantile=0.75, output_path=None):
    """Фильтрует точки по расстоянию от центроида плотности и сохраняет новый PLY"""
    with open(ply_path, 'rb') as f:
        header = b""
        while not header.endswith(b'end_header\n'):
            line = f.readline()
            header += line
        
        # Парсим заголовок
        header_text = header.decode('utf-8')
        vertex_count = int(re.search(r'element vertex (\d+)', header_text).group(1))
        
        props = re.findall(r'property (\w+) (\w+)', header_text)
        dtype_map = {'float': 'f4'}
        np_dtype = [(name, dtype_map[typ]) for typ, name in props]
        data = np.frombuffer(f.read(), dtype=np_dtype, count=vertex_count)

    # Вычисляем центроид и расстояния
    centroid = np.mean([data['x'], data['y'], data['z']], axis=1)
    positions = np.stack([data['x'], data['y'], data['z']], axis=1)
    distances = np.linalg.norm(positions - centroid, axis=1)
    
    # Применяем квантильный фильтр
    threshold = np.quantile(distances, density_quantile)
    mask = distances <= threshold
    
    filtered_data = data[mask]
    print(f"Filtered {len(filtered_data)}/{vertex_count} points ({(len(filtered_data)/vertex_count)*100:.1f}%)")

    # Генерируем выходной путь
    if not output_path:
        base, ext = os.path.splitext(ply_path)
        output_path = f"{base}_crop{ext or '.ply'}"
    
    # Обновляем заголовок и сохраняем
    new_header = re.sub(
        r'element vertex \d+',
        f'element vertex {len(filtered_data)}', 
        header_text
    )
    
    with open(output_path, 'wb') as f:
        f.write(new_header.encode('utf-8'))
        f.write(filtered_data.tobytes())
        
    return output_path