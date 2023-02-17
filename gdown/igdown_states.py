from .gdown_states import GDownStates


class IGDownStatesInterface:
    def changed(self, state: GDownStates, data={}):
        """Empty interface to report GDown state machine"""
        pass
