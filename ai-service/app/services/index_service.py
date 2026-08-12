from typing: Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ai_service.app.config import get_settings

settings = get_settings()


class IndexService:
    """Team Intelligence Index computation"""
    
    # Configurable weights
    WEIGHTS = {
        "health_score": 0.25,
        "risk_score": 0.25,  # Inverted
        "communication_score": 0.20,
        "workload_balance": 0.15,
        "memory_utilization": 0.15,
    }
    
    TIER_THRESHOLDS = {
        "Excellent": 90,
        "Good": 75,
        "Fair": 60,
        "Poor": 40,
        "Critical": 0,
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def compute_index(
        self,
        project_id: UUID,
        org_id: UUID,
    ) -> dict:
        """Compute Team Intelligence Index for a project"""
        
        # Get project health
        health_score = await self._get_health_score(project_id)
        
        # Get risk score (inverted)
        risk_score = await self._get_risk_score(project_id)
        
        # Get communication score
        comm_score = await self._get_communication_score(project_id)
        
        # Get workload balance
        workload_balance = await self._get_workload_balance(project_id)
        
        # Get memory utilization
        memory_util = await self._get_memory_utilization(org_id, project_id)
        
        # Calculate weighted score
        weighted_score = (
            health_score * self.WEIGHTS["health_score"] +
            (1 - risk_score) * self.WEIGHTS["risk_score"] +
            comm_score * self.WEIGHTS["communication_score"] +
            workload_balance * self.WEIGHTS["workload_balance"] +
            memory_util * self.WEIGHTS["memory_utilization"]
        )
        
        # Convert to 0-100 scale
        index_score = round(weighted_score * 100, 1)
        
        # Determine tier
        tier = "Critical"
        for t, threshold in self.TIER_THRESHOLDS.items():
            if index_score >= threshold:
                tier = t
                break
        
        return {
            "score": index_score,
            "tier": tier,
            "health_score": round(health_score, 2),
            "risk_score": round(risk_score, 2),
            "communication_score": round(comm_score, 2),
            "workload_balance": round(workload_balance, 2),
            "memory_utilization": round(memory_util, 2),
            "computed_at": datetime.utcnow().isoformat(),
            "weights": self.WEIGHTS,
        }
    
    async def _get_health_score(self, project_id: UUID) -> float:
        """Get project health score (0-1)"""
        # Would query from project table
        return 0.7
    
    async def _get_risk_score(self, project_id: UUID) -> float:
        """Get aggregate risk score (0-1)"""
        # Would aggregate from risk_scores table
        return 0.3
    
    async def _get_communication_score(self, project_id: UUID) -> float:
        """Get communication health score (0-1)"""
        # Would analyze communication events
        return 0.75
    
    async def _get_workload_balance(self, project_id: UUID) -> float:
        """Get workload balance score (0-1)"""
        # Would analyze workload snapshots
        return 0.8
    
    async def _get_memory_utilization(self, org_id: UUID, project_id: UUID) -> float:
        """Get organizational memory utilization score (0-1)"""
        # Would analyze memory entries
        return 0.6
    
    async def get_index_history(
        self,
        project_id: UUID,
        days: int = 30,
    ) -> list[dict]:
        """Get historical index values"""
        # Placeholder for time series data
        return [
            {"date": "2024-01-01", "score": 72, "tier": "Good"},
            {"date": "2024-01-08", "score": 75, "tier": "Good"},
            {"date": "2024-01-15", "score": 73, "tier": "Good"},
            {"date": "2024-01-22", "score": 76, "tier": "Good"},
        ]