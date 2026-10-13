"""Top-level package for the SAT-based economic model library.

The project intentionally keeps the implementation flat under src/ rather than a nested
package directory, as requested by the repository owner.
"""

from .decision import *
from .encodings import *
from .foundation import *
from .auctions import *
from .market import *
from .production import *
from .games import *
from .crypto import *
from .welfare import *
from .solver import *
