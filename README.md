# Monticello

Dynamic quantized mesh encoder extension for [Titiler](https://github.com/developmentseed/titiler).

Heavily adapted from and inspired by [dem-tiler](https://github.com/kylebarron/dem-tiler) 

only partially tested so far...

The word Monticello means "little mountain" or something close to that in Italian, playing off the naming of titiler to convey smallness 
and topography.

## Features

- supports both delatin and martini algorithms for generating meshes dynamically
- uses [quantized-mesh-encoder](https://github.com/kylebarron/quantized-mesh-encoder) for response
- supports variable tile sizes, buffer


## Usage

```python
app = FastAPI()
tiler = TilerFactory(
    router_prefix="/cog",
    extensions = [
        MonticelloFactory()
    ]
)
app.include_router(tiler.router, prefix="/cog")
# now meshes are available at /cog/mesh/
```
