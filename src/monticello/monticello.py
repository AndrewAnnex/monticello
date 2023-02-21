"""
Heavily adopted from https://github.com/kylebarron/dem-tiler/
"""
from typing import Optional, Literal, List, Tuple, Type
from dataclasses import dataclass, field
from io import BytesIO


from morecantile import tms as morecantile_tms
from morecantile.defaults import TileMatrixSets
import rasterio
from rio_tiler.errors import InvalidBufferSize
from rio_tiler.io import BaseReader, Reader
from quantized_mesh_encoder import encode as qme_encode
from pymartini import Martini, rescale_positions as martini_rescale_positions
from pydelatin import Delatin
from pydelatin.util import rescale_positions as delatin_rescale_positions


from fastapi import Depends, Query, Path, HTTPException
from titiler.core.factory import BaseTilerFactory, FactoryExtension
from titiler.core.dependencies import RescalingParams
from starlette.responses import Response


from .responses import QMEResponse, qme_responses


def tile_to_mesh_martini(tile, bounds, tile_size: int = 512, max_error: float = 10.0, flip_y: bool = False):
    martini = Martini(tile_size) 
    tin = martini.create_tile(tile)
    vrt, tri = tin.get_mesh(max_error=max_error)
    res = martini_rescale_positions(vrt, tile, bounds=bounds, flip_y=flip_y)
    return res, tri


def tile_to_mesh_delatin(tile, bounds, tile_size: int = 512, max_error: float = 10.0, flip_y: bool = False):
    tin = Delatin(tile, height=tile_size, width=tile_size, max_error=max_error)
    vrt, tri = tin.vertices, tin.triangles.flatten()
    res = delatin_rescale_positions(vrt, bounds, flip_y=flip_y)
    return res, tri


@dataclass
class MonticelloFactory(FactoryExtension):
    # Default reader is set to rio_tiler.io.Reader
    reader: Type[BaseReader] = Reader
    
    # TileMatrixSet dependency
    supported_tms: TileMatrixSets = morecantile_tms
    default_tms: str = "WebMercatorQuad"
    
    buffer: int = field(default=0)
    max_error: float = field(default=1.0)
    flip_y: str = field(default='False')
    
    def register(self, factory: BaseTilerFactory):
        """Register /mesh endpoint."""
        #todo, should I have .terrain extensions?
        @factory.router.get(r"/mesh/{z}/{x}/{y}", response_class=QMEResponse, responses=qme_responses)
        @factory.router.get(r"/mesh/{z}/{x}/{y}.{format}", response_class=QMEResponse, responses=qme_responses)
        @factory.router.get(r"/mesh/{z}/{x}/{y}@{scale}x", response_class=QMEResponse, responses=qme_responses)
        @factory.router.get(r"/mesh/{z}/{x}/{y}@{scale}x.{format}", response_class=QMEResponse, responses=qme_responses)
        @factory.router.get(r"/mesh/{TileMatrixSetId}/{z}/{x}/{y}", response_class=QMEResponse, responses=qme_responses)
        @factory.router.get(
            r"/mesh/{TileMatrixSetId}/{z}/{x}/{y}.{format}", response_class=QMEResponse, responses=qme_responses
        )
        @factory.router.get(
            r"/mesh/{TileMatrixSetId}/{z}/{x}/{y}@{scale}x", response_class=QMEResponse, responses=qme_responses
        )
        @factory.router.get(
            r"/mesh/{TileMatrixSetId}/{z}/{x}/{y}@{scale}x.{format}",
            response_class=QMEResponse, responses=qme_responses
        )
        def mesh(
                z: int = Path(..., ge=0, le=30, description="TMS tiles's zoom level"),
                x: int = Path(..., description="TMS tiles's column"),
                y: int = Path(..., description="TMS tiles's row"),
                TileMatrixSetId: Literal[tuple(factory.supported_tms.list())] = Query(
                    factory.default_tms,
                    description=f"TileMatrixSet Name (default: '{factory.default_tms}')",
                ),
                scale: int = Query(
                    2, gt=0, lt=4, description="Tile size scale. 1=256x256, 2=512x512..."
                ),
                src_path=Depends(factory.path_dependency),
                layer_params=Depends(factory.layer_dependency),
                dataset_params=Depends(factory.dataset_dependency),
                post_process=Depends(factory.process_dependency),
                buffer: Optional[float] = Query(
                    None,
                    gt=0,
                    title="Tile buffer.",
                    description="Buffer on each side of the given tile. It must be a multiple of `0.5`. Output **tilesize** will be expanded to `tilesize + 2 * buffer` (e.g 0.5 = 257x257, 1.0 = 258x258).",
                ),
                rescale: Optional[List[Tuple[float, ...]]] = Depends(RescalingParams),
                reader_params=Depends(factory.reader_dependency),
                env=Depends(factory.environment_dependency),
                mesh_quantizer: Literal['martini', 'delatin'] = Query("delatin", description="Mesh encoding algorithm to use")
        ):
            tms = self.supported_tms.get(TileMatrixSetId)
            tilesize = scale * 256
            with rasterio.Env(**env):
                with self.reader(src_path, tms=tms, **reader_params) as src_dst:
                    # todo raise error if buffer not gt 0 and martini tiler
                    try:
                        image = src_dst.tile(
                           x,
                           y,
                           z,
                           tilesize=tilesize,
                           buffer=buffer,
                           **layer_params,
                           **dataset_params,
                        )
                    except InvalidBufferSize:
                        raise HTTPException(
                            status_code=422,
                            detail=f"Buffer '{buffer}' invalid, must be GT 0 and a multiple of 0.5"
                        )
            if post_process:
                image = post_process(image)
            if rescale:
                image = image.rescale(rescale)
            # got the tile data, now do the work
            flip_y: bool = self.flip_y[0].lower() == 'true'
            tile = image.data[0]
            tile_size: int = tile.shape[0]
            bounds = image.bounds
            if mesh_quantizer == 'delatin':
                res, tri = tile_to_mesh_delatin(
                    tile,
                    bounds,
                    tile_size=tile_size,
                    max_error=self.max_error,
                    flip_y=flip_y
                )
            else:
                res, tri = tile_to_mesh_martini(
                    tile,
                    bounds,
                    tile_size=tile_size,
                    max_error=self.max_error,
                    flip_y=flip_y
                )


            with BytesIO() as out:
                qme_encode(out, res, tri)
                out.seek(0)
                return Response(out.read(), media_type="application/vnd.quantized-mesh")
