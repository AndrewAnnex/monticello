import os
from fastapi import Depends, FastAPI, HTTPException, Path, Query
from starlette.testclient import TestClient
from titiler.core.factory import TilerFactory
from ..monticello import MonticelloFactory
import rasterio as rio
import rasterio.warp
import morecantile

import pytest

DATA_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
with rio.open(f'{DATA_DIR}/dem.tif') as dem:
    dem_crs = dem.crs
    dem_bounds = dem.bounds

crs4326 = rio.crs.CRS.from_epsg(code=4326)
dem_bounds_4326 = rio.warp.transform_bounds(dem_crs, crs4326, *dem_bounds)
dem_lon = (dem_bounds_4326[0] + dem_bounds_4326[2]) / 2 
dem_lat = (dem_bounds_4326[1] + dem_bounds_4326[3]) / 2 
tms = morecantile.tms.get("WebMercatorQuad")
tms12 = tms.tile(dem_lon, dem_lat, 12)
tms13 = tms.tile(dem_lon, dem_lat, 13)
tms14 = tms.tile(dem_lon, dem_lat, 14)


def test_MonticelloFactory():
    app = FastAPI()
    tiler = TilerFactory(
        router_prefix="/cog",
        extensions = [
            MonticelloFactory()
        ]
    )
    app.include_router(tiler.router, prefix="/cog")
    client = TestClient(app)

    # test delatin
    response = client.get(
        f"/cog/mesh/{tms13.z}/{tms13.x}/{tms13.y}",
        params = {
            "url": f"{DATA_DIR}/dem.tif",
            "mesh_quantizer": "delatin"
        }
    )
    assert response.status_code == 200
    
    # test martini with buffer 0.5
    response = client.get(
        f"/cog/mesh/{tms13.z}/{tms13.x}/{tms13.y}",
        params = {
            "url": f"{DATA_DIR}/dem.tif",
            "mesh_quantizer": "martini",
            "buffer": 0.5
        }
    )
    assert response.status_code == 200
    
    # test martini with buffer 0.5 and flipy
    response = client.get(
        f"/cog/mesh/{tms13.z}/{tms13.x}/{tms13.y}",
        params = {
            "url": f"{DATA_DIR}/dem.tif",
            "mesh_quantizer": "martini",
            "buffer": 0.5,
            "flip_y": "True",
        }
    )
    assert response.status_code == 200
    
    # test martini without a buffer, should throw an exception
    response = client.get(
        f"/cog/mesh/{tms13.z}/{tms13.x}/{tms13.y}",
        params = {
            "url": f"{DATA_DIR}/dem.tif",
            "mesh_quantizer": "martini",
            "buffer": 0
        }
    )
    assert response.status_code == 422
        
    # test martini with a buffer that is an even number, should throw an exception
    response = client.get(
        f"/cog/mesh/{tms13.z}/{tms13.x}/{tms13.y}",
        params = {
            "url": f"{DATA_DIR}/dem.tif",
            "mesh_quantizer": "martini",
            "buffer": 0.2
        }
    )
    assert response.status_code == 422
