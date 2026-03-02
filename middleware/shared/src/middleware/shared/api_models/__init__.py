"""FAIRagro Middleware API Models package.

Backward compatibility layer for refactored shared models.
"""

from .common import models as common
from .v1 import models as v1
from .v2 import models as v2

# Common / Shared
ArcStatus = common.ArcStatus
TaskStatus = common.TaskStatus
ApiResponse = common.ApiResponse
ArcResponse = common.ArcResponse  # V1/V2 common

# V1 Models
LivenessResponse = v1.LivenessResponse
HealthResponse = v1.HealthResponse
CreateOrUpdateArcsRequest = v1.CreateOrUpdateArcsRequest
CreateOrUpdateArcsResponse = v1.CreateOrUpdateArcsResponse
GetTaskStatusResponse = v1.GetTaskStatusResponse
WhoamiResponse = v1.WhoamiResponse
ArcTaskTicket = v1.ArcTaskTicket

# V2 Models
HealthResponseV2 = v2.HealthResponse
CreateOrUpdateArcRequest = v2.CreateOrUpdateArcRequest
CreateOrUpdateArcResponse = v2.CreateOrUpdateArcResponse
ArcOperationResult = v2.ArcOperationResult
GetTaskStatusResponseV2 = v2.GetTaskStatusResponse
