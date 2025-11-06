from dataclasses import dataclass

@dataclass
class IgnData:
    username: str

@dataclass
class IdentityData:
    name: str

@dataclass
class Player:
    puuid: str
    team_id: str
    ign: IgnData
    identity: IdentityData

@dataclass
class MatchDetails:
    game_mode: str
    map_name: str
    server: str
