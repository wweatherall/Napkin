"""Simulate the wave-front controller to tune smoothness before porting to GDScript."""
import math, sys

def run(slow, ta, tb, ta_up, tb_up, dt=1/30, t_ok=5.4, dur=0.884, hold=0.6, lo=0.3, bw=2.4, T=7.0, two_stage=True):
    v0 = 1/dur
    p = 0.0; v1 = v0; v = v0; ph = 0.0; state = "pending"
    out = []
    t = 0.0
    while t < T:
        t += dt
        if t >= t_ok: state = "ok"
        breathing = ph > 0
        if state == "pending":
            goal = hold
            if breathing:
                mid = (hold + lo) / 2
                goal = mid + (hold - mid) * math.cos(ph)
            c = v0 * max(-1, min(1, (goal - p) / slow))
        else:
            c = v0
        a_, b_ = (ta_up, tb_up) if state == "ok" else (ta, tb)
        v1 += (c - v1) * (1 - math.exp(-dt / a_))
        if two_stage:
            v += (v1 - v) * (1 - math.exp(-dt / b_))
        else:
            v = v1
        p += v * dt
        if state == "pending" and (breathing or abs(v) < 0.15 * v0):
            ph += bw * dt
        out.append((t, p, v))
    return out

def metrics(out, dt):
    v = [o[2] for o in out]
    acc = [(v[i+1]-v[i])/dt for i in range(len(v)-1)]
    jerk = [(acc[i+1]-acc[i])/dt for i in range(len(acc)-1)]
    ps = [o[1] for o in out if 1.2 < o[0] < 5.3]
    first_peak = max(o[1] for o in out if o[0] < 1.5)
    return dict(max_acc=max(abs(a) for a in acc), max_jerk=max(abs(j) for j in jerk),
                lo=min(ps), hi=max(ps), first_peak=first_peak)

if __name__ == "__main__":
    dt = 1/120
    for name, args in [("current (1 stage)", dict(slow=0.15, ta=0.08, tb=0.0, ta_up=0.18, tb_up=0.0, two_stage=False)),
                       ("2-stage A", dict(slow=0.25, ta=0.10, tb=0.10, ta_up=0.18, tb_up=0.18)),
                       ("2-stage B", dict(slow=0.30, ta=0.12, tb=0.12, ta_up=0.20, tb_up=0.20)),
                       ("2-stage C", dict(slow=0.35, ta=0.10, tb=0.14, ta_up=0.20, tb_up=0.22))]:
        m = metrics(run(dt=dt, **args), dt)
        print(f"{name:20s} max|acc| {m['max_acc']:.2f}  max|jerk| {m['max_jerk']:8.1f}  range {m['lo']:.3f}-{m['hi']:.3f}  first peak {m['first_peak']:.3f}")
