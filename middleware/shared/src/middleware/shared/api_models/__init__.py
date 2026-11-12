"""FAIRagro Middleware API Models package.

Backward compatibility layer for refactored shared models.
"""

from .common import models as common
from .v2 import models as v2

# Common / Shared
ArcStatus = common.ArcStatus
TaskStatus = common.TaskStatus
ApiResponse = common.ApiResponse
ArcResponse = common.ArcResponse  # shared by v2 BL / compatibility exports

# V2 Models
HealthResponseV2 = v2.HealthResponse
CreateOrUpdateArcRequest = v2.CreateOrUpdateArcRequest
CreateOrUpdateArcResponse = v2.CreateOrUpdateArcResponse
ArcOperationResult = v2.ArcOperationResult
GetTaskStatusResponseV2 = v2.GetTaskStatusResponse
