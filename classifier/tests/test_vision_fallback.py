"""Cloud scheduling/contract tests: no API calls, no paid tokens, no camera files."""
import json
import unittest
from unittest.mock import patch
from PIL import Image
from kinevoa_classifier.vision_fallback import VisionFallback,Settings,VisionError,request_vision,canonical_exercise

class Deferred:
    def __init__(self):self.jobs=[]
    def submit(self,fn,*args):self.jobs.append((fn,args))
    def run(self):
        while self.jobs:
            fn,args=self.jobs.pop(0);fn(*args)
    def shutdown(self,**kw):self.jobs=[]

class CloudTests(unittest.TestCase):
    def setup_model(self,labels=('squat','squat'),max_calls=30,enabled=True):
        self.t=0;self.executor=Deferred();self.requests=[];labels=iter(labels)
        def request(config,frames):self.requests.append(tuple(frames));return next(labels)
        self.model=VisionFallback(lambda:Settings('fake-key',enabled,max_calls=max_calls),request,lambda:self.t,self.executor)
        self.image=Image.new('RGB',(80,160),'white')
    def frame(self,t,key='session'):
        self.t=t;return self.model.update(key,self.image)
    def test_trigger_after_twenty_and_require_disjoint_fresh_frames(self):
        self.setup_model()
        for t in range(20):self.frame(t)
        self.assertEqual(len(self.executor.jobs),0)
        self.assertEqual(self.frame(20)['cloud_status'],'checking')
        self.executor.run()
        first=self.model.sessions['session'].last_cutoff
        self.assertEqual(self.frame(21)['cloud_status'],'awaiting_fresh_frames')
        for t in range(22,26):self.frame(t)
        self.assertEqual(len(self.executor.jobs),0)
        self.assertEqual(self.frame(26)['cloud_status'],'checking_again')
        self.assertGreater(self.model.sessions['session'].frames[0][0],first)
        self.executor.run();result=self.frame(27)
        self.assertEqual(result['exercise'],'squat');self.assertEqual(result['display_name'],'Squat')
        self.assertTrue(result['cloud_confirmed']);self.assertEqual(result['cloud_checks'],2)
        self.assertEqual(len(self.requests),2)
        for t in range(28,100):self.frame(t)
        self.assertEqual(len(self.requests),2)
    def test_locally_resolved_session_never_uses_paid_fallback(self):
        self.setup_model()
        for t in range(60):
            self.t=t
            result=self.model.update('session',self.image,local_exercise='squat')
        self.assertEqual(result['cloud_status'],'local_confirmed')
        self.assertEqual(self.model.calls,0)
        self.assertEqual(len(self.model.sessions['session'].frames),0)

    def test_unknown_never_confirms_and_stops_retries(self):
        self.setup_model(labels=(None,))
        for t in range(21):self.frame(t)
        self.executor.run()
        for t in range(21,50):r=self.frame(t)
        self.assertNotIn('cloud_confirmed',r);self.assertEqual(r['cloud_status'],'uncertain')
        self.assertEqual(self.model.calls,1)
    def test_disagreement_never_confirms(self):
        self.setup_model(labels=('squat','pushup'))
        for t in range(21):self.frame(t)
        self.executor.run()
        for t in range(21,27):self.frame(t)
        self.executor.run()
        self.assertEqual(self.frame(27)['cloud_status'],'disagreement')
    def test_disabled_does_not_buffer_or_call(self):
        self.setup_model(enabled=False)
        for t in range(100):self.frame(t)
        self.assertEqual(len(self.model.sessions),0);self.assertEqual(len(self.requests),0)
    def test_sessions_do_not_share_time_or_confirmation(self):
        self.setup_model()
        for t in range(21):self.frame(t,'a')
        self.executor.run();self.assertEqual(self.frame(21,'b')['cloud_status'],'waiting')
        self.assertIsNone(self.model.sessions['b'].candidate)
    def test_request_budget_and_pending_single_flight(self):
        self.setup_model(max_calls=1)
        for t in range(50):self.frame(t)
        self.assertEqual(self.model.calls,1);self.assertEqual(len(self.executor.jobs),1)
        self.executor.run()
        for t in range(50,58):r=self.frame(t)
        self.assertEqual(r['cloud_status'],'budget_reached');self.assertEqual(self.model.calls,1)
    def test_old_completion_does_not_reenter_evicted_session(self):
        self.setup_model()
        for t in range(21):self.frame(t,'a')
        for i in range(9):self.frame(21,str(i))
        self.executor.run();self.assertNotIn('a',self.model.sessions)
        self.assertLessEqual(len(self.model.sessions),8)
    def test_safe_unmapped_names(self):
        self.assertIsNone(canonical_exercise('Bulgarian split squat'))
        self.assertEqual(canonical_exercise('push-ups'),'pushup')
        for value in ['unknown','standing','<script>alert(1)</script>','x'*100]:self.assertIsNone(canonical_exercise(value))
    def test_openai_payload_and_response(self):
        response={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'exercise':'Biceps curls','evidence':'clear','motion_observed':True})}]}]}
        with patch('kinevoa_classifier.vision_fallback.requests.post') as post:
            post.return_value.status_code=200;post.return_value.json.return_value=response
            label=request_vision(Settings('secret',True),[b'jpeg']*6)
            self.assertIsNone(label);payload=post.call_args.kwargs['json']
            self.assertFalse(payload['store']);self.assertEqual(payload['model'],'gpt-5.4-nano')
            self.assertEqual(len(payload['input'][0]['content']),7)
            self.assertTrue(payload['text']['format']['strict'])
    def test_errors_are_sanitised_and_model_cannot_supply_confidence(self):
        with patch('kinevoa_classifier.vision_fallback.requests.post') as post:
            post.return_value.status_code=401
            with self.assertRaisesRegex(VisionError,'^authentication_failed$'):request_vision(Settings('secret',True),[b'x']*6)
        self.assertNotIn('secret',repr(Settings('secret',True)))
        self.assertNotIn('confidence',__import__('kinevoa_classifier.vision_fallback',fromlist=['SCHEMA']).SCHEMA['properties'])
if __name__=='__main__':unittest.main()
