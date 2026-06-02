"""Hybrid position matcher for reference profile lookup.

Two-stage algorithm:
1. Sequential locality scan around last_index (O(1) amortized)
2. Full 3D position relocalization on dist_traveled discontinuity (O(n))
"""


def _dist3d_sq(frame, pos):
    return ((frame.pos_x - pos[0]) ** 2 +
            (frame.pos_y - pos[1]) ** 2 +
            (frame.pos_z - pos[2]) ** 2)


class ProfileMatcher:

    DISCONTINUITY_THRESHOLD = -50.0  # meters — negative delta triggers relocalization
    MAX_MATCH_DISTANCE_SQ = 40000.0  # 200m squared — reject if too far
    FORWARD_WINDOW = 100             # frames to scan forward
    BACKWARD_WINDOW = 20             # frames to scan backward

    def __init__(self, profile):
        self.profile = profile
        self.frames = profile.frames
        self.last_index = 0
        self.prev_dist = 0.0
        self.initialized = False

    def match(self, fdp):
        if not self.frames:
            return None, 0

        current_dist = fdp.dist_traveled
        current_pos = (fdp.position_x, fdp.position_y, fdp.position_z)

        if not self.initialized:
            self.prev_dist = current_dist
            result, idx = self._relocalize(current_pos)
            if result is not None:
                self.last_index = idx
                self.initialized = True
            return result, idx

        dist_delta = current_dist - self.prev_dist
        self.prev_dist = current_dist

        if dist_delta < self.DISCONTINUITY_THRESHOLD:
            result, idx = self._relocalize(current_pos)
            if result is not None:
                self.last_index = idx
            return result, idx

        result, idx = self._locality_scan(current_pos)
        if result is not None:
            self.last_index = idx
        return result, idx

    def _locality_scan(self, current_pos):
        scan_start = max(0, self.last_index - self.BACKWARD_WINDOW)
        scan_end = min(len(self.frames), self.last_index + self.FORWARD_WINDOW)

        best_idx = self.last_index
        best_dist_sq = float('inf')

        for i in range(scan_start, scan_end):
            dsq = _dist3d_sq(self.frames[i], current_pos)
            if dsq < best_dist_sq:
                best_dist_sq = dsq
                best_idx = i

        if best_dist_sq > self.MAX_MATCH_DISTANCE_SQ:
            return None, self.last_index

        return self.frames[best_idx], best_idx

    def _relocalize(self, current_pos):
        if not self.frames:
            return None, 0

        best_idx = 0
        best_dist_sq = float('inf')

        for i, f in enumerate(self.frames):
            dsq = _dist3d_sq(f, current_pos)
            if dsq < best_dist_sq:
                best_dist_sq = dsq
                best_idx = i

        if best_dist_sq > self.MAX_MATCH_DISTANCE_SQ:
            return None, 0

        return self.frames[best_idx], best_idx

    def reset(self):
        self.last_index = 0
        self.prev_dist = 0.0
        self.initialized = False
