import random
import time

MODULES = [
    "core/arena", "core/strings", "core/hash", "geo/point", "geo/bbox", "geo/projection", "geo/haversine",
    "tiles/encoder", "tiles/quadkey", "tiles/cache", "tiles/raster", "tiles/vector", "roads/graph",
    "roads/contract", "roads/astar", "roads/turns", "labels/placer", "labels/collide", "labels/shaping",
    "search/trie", "search/fuzzy", "search/rank", "io/mmap", "io/protobuf", "io/zstd", "io/http",
    "render/raster", "render/sdf", "render/atlas", "export/geojson", "export/mvt", "export/pmtiles",
    "cli/main", "cli/args",
]

total = len(MODULES) + 2
random.seed(7)
for i, module in enumerate(MODULES, 1):
    print(f"[{i}/{total}] CC src/{module}.c", flush=True)
    time.sleep(0.35 + random.random() * 0.5)
print(f"[{total - 1}/{total}] AR build/libatlas.a", flush=True)
time.sleep(1.2)
print(f"[{total}/{total}] LD build/atlas", flush=True)
time.sleep(1.5)
