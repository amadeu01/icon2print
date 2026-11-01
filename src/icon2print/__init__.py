"""icon2print: 2D icon -> 3D printable STL."""
from .outline import load_icon, normalize
from .models import extrude, make_box, BoxParams, BoxResult

__all__ = ["load_icon", "normalize", "extrude", "make_box", "BoxParams", "BoxResult"]
__version__ = "0.1.0"
