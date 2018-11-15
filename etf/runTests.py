import json
import requests
import time
import csv
import os
import check_qa

endpoint = 'http://10.0.30.63:9999/etf-webapp/v2/'

test_id = 'EID8222c253-8468-4b94-a46b-2d1af1698a65'  # Conformance Class: 'GML application schema, Protected Sites'

assertions = {}
assertions_ordered = []
assertions_filled = False
test_files_base = 'E:/inspire/reliability'

do_not_run = ['1dc22f5a6bfd44a99f6380b516cbc96e', '641340fe18924ce9964023e7665ca44c', '6000e9d1e97f4692ba92edb889b00661', '6eaf2aaf7f3f47b0b3822c11f52d53bf', '92dafefe04b041b2b44883292421893e', 'c660150e866f45f0902a2ee89e95f514', 'c2916b37700547e199cf37663adefe27']


# server cleanup
def delete_all():
    all_tests = requests.get(endpoint + 'TestRuns').json()
    if 'testRuns' in all_tests['EtfItemCollection']:
        for tr in all_tests['EtfItemCollection']['testRuns']['TestRun']:
            print('Deleting ', tr['id'], 'with status', tr['status'])
            del_resp = requests.delete(endpoint + 'TestRuns/' + tr['id'])
            print('  ', del_resp.status_code)


# delete the run
def delete_run(run_id):
    del_resp = requests.delete(endpoint + 'TestRuns/' + run_id)
    return del_resp.status_code


# if it's not a list, wrap it - as the json is not consistent
def to_list(list_or_dict):
    if isinstance(list_or_dict, dict):
        return [list_or_dict]
    return list_or_dict


# runs one test; the result is a list
def run_for_file(test_file):
    global assertions_filled
    global assertions_ordered
    global assertions

    delay = 10  # seconds between checks
    timeout = 10*60  # seconds

    result = []
    content_type = 'application/zip' if '.zip' in test_file else 'text/xml'
    upload_request = {'file': ('test.xml', open(test_file, 'rb'), content_type)}

    print('   Upload request:', upload_request)

    upload_response = requests.post(endpoint + 'TestObjects?action=upload', files=upload_request).json()

    print('   Upload response:', upload_response)

    if 'testObject' in upload_response:
        file_id = upload_response['testObject']['id']
        print('   File id:', file_id)

        tests_to_execute = '^(gml\.a\.[0-9]|ps-gml\.a\.[0-9]|gmlas\.a\.[0-9]|gmlas\.b\.[0-9]|gmlas\.c\.[0-9]|gmlas\.e\.[0-9]|gmlas\.f\.[0-9]|gmlas\.d\.[1-9]|gmlas\.d\.11):.*'

        test_request = {'label': 'My test', 'executableTestSuiteIds': [test_id], 'arguments': {'files_to_test': '.*', 'tests_to_execute': tests_to_execute}, 'testObject': {'id': file_id}}

        # print('   Sending request:', json.dumps(test_request))

        test_run_raw = requests.post(endpoint + 'TestRuns', json=test_request)
        test_run = test_run_raw.json()
        # print(test_run)

        test_run_id = test_run['EtfItemCollection']['testRuns']['TestRun']['id']
        print('   Test run ID:', test_run_id)

        progress_response = {'val': 0, 'max': 1}

        iterations = 0
        initializing_found = False

        while int(progress_response['val']) < int(progress_response['max']) and iterations < timeout/delay:
            time.sleep(delay)
            iterations += 1
            progress_response = requests.get(endpoint + 'TestRuns/' + test_run_id + '/progress?pos=0').json()
            print('     progress:', progress_response['val'], 'of', progress_response['max'], 'in', iterations*delay, 'seconds --', progress_response['log'][-1] if len(progress_response['log']) > 0 else '')
            # print(progress_response['log'])
            if len(progress_response['log']) > 0 and 'CREATED to INITIALIZING' in progress_response['log'][-1]:
                # stuck?
                if initializing_found:
                    # yes
                    print('!!! Stuck threads!')
                    result.append('Threads stuck!')
                    return result
                else:
                    # not yet
                    initializing_found = True

        if iterations < timeout/delay:

            print('     progress:', progress_response)
            end_results_a = requests.get(endpoint + 'TestRuns/' + test_run_id)

            if end_results_a.status_code != 200:
                return ['HTTP error: ' + str(end_results_a.status_code)]

            end_results = end_results_a.json()

            # print end_results

            if not assertions:
                for ets in end_results['EtfItemCollection']['referencedItems']['executableTestSuites']['ExecutableTestSuite']:
                    for tm in to_list(ets['testModules']['TestModule']):
                        for tc in to_list(tm['testCases']['TestCase']):
                            for ts in to_list(tc['testSteps']['TestStep']):
                                for ta in to_list(ts['testAssertions']['TestAssertion']):
                                    assertions[ta['id']] = ta['label']

            # print assertions
            # print

            for end_result in to_list(end_results['EtfItemCollection']['referencedItems']['testTaskResults']['TestTaskResult']):
                for module_result in to_list(end_result['testModuleResults']['TestModuleResult']):
                    for case_result in to_list(module_result['testCaseResults']['TestCaseResult']):
                        for step_result in to_list(case_result['testStepResults']['TestStepResult']):
                            for assertion_result in to_list(step_result['testAssertionResults']['TestAssertionResult']):
                                print('   Result:', assertions[assertion_result['resultedFrom']['ref']], assertion_result['status'])
                                result.append(assertion_result['status'])
                                if not assertions_filled:
                                    assertions_ordered.append(assertions[assertion_result['resultedFrom']['ref']])

            assertions_filled = True

        else:
            result.append('Timeout on test')
            print('  !Timeout')

        delete_result = delete_run(test_run_id)
        print('   Test deleted:', delete_result)

    return result


def list_files(base_dir):
    result = []
    for country in [x for x in os.listdir(base_dir) if os.path.isdir(base_dir + '/' + x)]:
        cpath = base_dir + '/' + country
        for dataset in [x for x in os.listdir(cpath) if os.path.isdir(cpath + '/' + x)]:
            # if dataset in do_not_run:
            #     continue

            dpath = cpath + '/' + dataset
            latest_file = max([dpath + '/' + x for x in os.listdir(dpath) if os.path.isdir(dpath + '/' + x)], key=os.path.getctime)
            # print latest_file
            files = [latest_file + '/' + x for x in os.listdir(latest_file) if 'diff' not in x and 'zip' not in x]
            result.extend(files)

    return result


def main():

    assertions_ordered.insert(0, ' ')
    assertions_ordered.append('schema checks')
    all_results = [assertions_ordered]

    # print(run_for_file('E:/inspire/reliability/CZ/bb76b77edfd34c29bc18c557ce5a11f9/20180928_203728/download'))
    # return

    with open('results.csv', 'w') as csvfile:
        resultwriter = csv.writer(csvfile)
        resultwriter.writerow(assertions_ordered)

        for f in list_files(test_files_base):
            print('File:', f)
            r = []
            # try:
            #     r = run_for_file(f)
            # except Exception as err:
            #     r.append(str(err))
            #     print('  !Test error:', err)

            r.insert(0, f)

            if 'stuck' in r[-1]:
                text = input("!!!!Please restart ETF; if you want to quit enter q")
                if 'q' in text:
                    break

            try:
                schema_result = check_qa.process_file(f)
                r.append(schema_result)
                print('   Schema test result:', schema_result)
            except Exception as err:
                r.append(str(err))
                print('  !Schema test error:', err)

            try:
                proposed_result = check_qa.count_proposed(f)
                r.extend(proposed_result)
                print('   Schema proposed count:', proposed_result)
            except Exception as err:
                r.append(str(err))
                print('  !Schema proposed error:', err)

            all_results.append(r)
            if len(r) > 0:
                print(r)
                resultwriter.writerow(r)


    # transpose
    all_results_t = [[all_results[j][i] for j in range(len(all_results))] for i in range(len(all_results[0]))]

    with open('results_t.csv', 'w') as csvfile:
        resultwriter = csv.writer(csvfile)
        for r in all_results_t:
            resultwriter.writerow(r)


if __name__ == "__main__":
    main()
