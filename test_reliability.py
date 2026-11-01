import unittest
from reliability import PeerHealth, OrderedControls, PlaybackEvidence

class ReliabilityTests(unittest.TestCase):
    def test_failure_threshold_and_recovery(self):
        now=[0.]
        h=PeerHealth(lambda:now[0]);h.success(dict(ready=True))
        now[0]=5;h.failure('network');self.assertEqual(h.snapshot()['status'],'reconnecting')
        now[0]=10;h.failure('network');self.assertEqual(h.snapshot()['status'],'reconnecting')
        now[0]=16;h.failure('network');self.assertEqual(h.snapshot()['status'],'offline')
        h.success(dict(ready=False));self.assertTrue(h.snapshot()['online']);self.assertFalse(h.snapshot()['ready'])

    def test_duplicate_reordered_and_expired_controls(self):
        order=OrderedControls();applied=[]
        def op(seq,issued=100):return dict(session='a'*32,seq=seq,issued=issued)
        self.assertTrue(order.apply(op(2),lambda:applied.append(2),100))
        self.assertFalse(order.apply(op(2),lambda:applied.append(2),100))
        self.assertFalse(order.apply(op(1),lambda:applied.append(1),100))
        with self.assertRaises(ValueError):order.apply(op(3,90),lambda:applied.append(3),100)
        self.assertEqual(applied,[2])

    def test_failed_control_can_be_retried_once(self):
        order=OrderedControls();op=dict(session='b'*32,seq=1,issued=100)
        def fail():raise RuntimeError()
        with self.assertRaises(RuntimeError):order.apply(op,fail,100)
        self.assertTrue(order.apply(op,lambda:None,100))

    def test_sender_pause_overrides_stale_mpris(self):
        p=PlaybackEvidence();info={'kMRMediaRemoteNowPlayingInfoTitle':'Song','kMRMediaRemoteNowPlayingInfoPlaybackRate':0.,'kMRMediaRemoteNowPlayingInfoElapsedTime':12}
        self.assertEqual(p.resolve(True,'Playing',info,'Song')[:2],('Paused',12))
        info['kMRMediaRemoteNowPlayingInfoPlaybackRate']=1.
        self.assertEqual(p.resolve(True,'Paused',info,'Song')[0],'Playing')
        p.event_received('paus');self.assertEqual(p.resolve(True,'Playing',info,'Song')[0],'Paused')
        p.event_received('prsm');self.assertEqual(p.resolve(True,'Paused',info,'Song')[0],'Playing')
        self.assertEqual(p.resolve(False,'Playing',info,'Song')[0],'Stopped')

    def test_flush_silence_and_missing_evidence(self):
        p=PlaybackEvidence();p.event_received('pfls')
        self.assertEqual(p.resolve(True,'Playing',{},'Song')[0],'Playing')
        self.assertEqual(p.resolve(True,'Stopped',{},'Song')[0],'Unknown')
        p.event_received('pend');self.assertEqual(p.resolve(True,'Playing',{},'Song')[0],'Unknown')
        p.event_received('pbeg');self.assertEqual(p.resolve(True,'Stopped',{},'Song')[0],'Playing')

if __name__=='__main__':unittest.main()
