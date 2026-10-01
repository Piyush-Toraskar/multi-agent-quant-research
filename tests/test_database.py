def test_roundtrip(repository,request_data):
    identifier=repository.create(request_data)
    repository.update(identifier,status='completed',result={'hello':'world'})
    row=repository.get(identifier)
    assert row['result']=={'hello':'world'} and row['status']=='completed'


def test_search_is_literal_and_parameterised(repository,request_data):
    repository.create(request_data)
    assert repository.search("' OR 1=1 --")==[]
    assert repository.search('%')==[]
    assert len(repository.search('AAPL'))==1


def test_event_ordering(repository,request_data):
    identifier=repository.create(request_data)
    repository.event(identifier,'data','start',{})
    repository.event(identifier,'data','end',{'rows':10})
    events=repository.events(identifier)
    assert [e['kind'] for e in events]==['start','end']
    assert len(repository.events(identifier,events[0]['id']))==1


def test_recover_interrupted(repository,request_data):
    identifier=repository.create(request_data)
    repository.recover_interrupted()
    assert repository.get(identifier)['status']=='interrupted'
