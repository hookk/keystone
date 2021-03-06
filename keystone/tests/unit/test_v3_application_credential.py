# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime
from testtools import matchers
import uuid

from six.moves import http_client

from keystone.common import provider_api
import keystone.conf
from keystone.tests import unit
from keystone.tests.unit import test_v3


CONF = keystone.conf.CONF
PROVIDERS = provider_api.ProviderAPIs
MEMBER_PATH_FMT = '/users/%(user_id)s/application_credentials/%(app_cred_id)s'


class ApplicationCredentialTestCase(test_v3.RestfulTestCase):
    """Test CRUD operations for application credentials."""

    def config_overrides(self):
        super(ApplicationCredentialTestCase, self).config_overrides()
        self.config_fixture.config(group='auth',
                                   methods='password,application_credential')

    def _app_cred_body(self, roles=None, name=None, expires=None, secret=None):
        name = name or uuid.uuid4().hex
        description = 'Credential for backups'
        app_cred_data = {
            'name': name,
            'description': description
        }
        if roles:
            app_cred_data['roles'] = roles
        if expires:
            app_cred_data['expires_at'] = expires
        if secret:
            app_cred_data['secret'] = secret
        return {'application_credential': app_cred_data}

    def test_create_application_credential(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            app_cred_body = self._app_cred_body(roles=roles)
            token = self.get_scoped_token()
            resp = c.post('/v3/users/%s/application_credentials' % self.user_id,
                          json=app_cred_body,
                          expected_status_code=http_client.CREATED,
                          headers={'X-Auth-Token': token})
        # Create operation returns the secret
        self.assertIn('secret', resp.json['application_credential'])
        # But not the stored hash
        self.assertNotIn('secret_hash', resp.json['application_credential'])

    def test_create_application_credential_with_secret(self):
        with self.test_client() as c:
            secret = 'supersecuresecret'
            roles = [{'id': self.role_id}]
            app_cred_body = self._app_cred_body(roles=roles, secret=secret)
            token = self.get_scoped_token()
            resp = c.post('/v3/users/%s/application_credentials' % self.user_id,
                          json=app_cred_body,
                          expected_status_code=http_client.CREATED,
                          headers={'X-Auth-Token': token})
        self.assertEqual(secret, resp.json['application_credential']['secret'])

    def test_create_application_credential_roles_from_token(self):
        with self.test_client() as c:
            app_cred_body = self._app_cred_body()
            token = self.get_scoped_token()
            resp = c.post('/v3/users/%s/application_credentials' % self.user_id,
                          json=app_cred_body,
                          expected_status_code=http_client.CREATED,
                          headers={'X-Auth-Token': token})
            self.assertThat(resp.json['application_credential']['roles'],
                            matchers.HasLength(1))
            self.assertEqual(resp.json['application_credential']['roles'][0]['id'],
                             self.role_id)

    def test_create_application_credential_wrong_user(self):
        wrong_user = unit.create_user(PROVIDERS.identity_api,
                                      test_v3.DEFAULT_DOMAIN_ID)
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            app_cred_body = self._app_cred_body(roles=roles)
            token = self.get_scoped_token()
            c.post('/v3/users/%s/application_credentials' % wrong_user['id'],
                   json=app_cred_body,
                   expected_status_code=http_client.FORBIDDEN,
                   headers={'X-Auth-Token': token})

    def test_create_application_credential_bad_role(self):
        with self.test_client() as c:
            roles = [{'id': uuid.uuid4().hex}]
            app_cred_body = self._app_cred_body(roles=roles)
            token = self.get_scoped_token()
            c.post('/v3/users/%s/application_credentials' % self.user_id,
                   json=app_cred_body,
                   expected_status_code=http_client.BAD_REQUEST,
                   headers={'X-Auth-Token': token})

    def test_create_application_credential_with_expiration(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            expires = datetime.datetime.utcnow() + datetime.timedelta(days=365)
            expires = str(expires)
            app_cred_body = self._app_cred_body(roles=roles, expires=expires)
            token = self.get_scoped_token()
            c.post('/v3/users/%s/application_credentials' % self.user_id,
                   json=app_cred_body,
                   expected_status_code=http_client.CREATED,
                   headers={'X-Auth-Token': token})

    def test_create_application_credential_invalid_expiration_fmt(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            expires = 'next tuesday'
            app_cred_body = self._app_cred_body(roles=roles, expires=expires)
            token = self.get_scoped_token()
            c.post('/v3/users/%s/application_credentials' % self.user_id,
                   json=app_cred_body,
                   expected_status_code=http_client.BAD_REQUEST,
                   headers={'X-Auth-Token': token})

    def test_create_application_credential_already_expired(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            expires = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
            app_cred_body = self._app_cred_body(roles=roles, expires=expires)
            token = self.get_scoped_token()
            c.post('/v3/users/%s/application_credentials' % self.user_id,
                   json=app_cred_body,
                   expected_status_code=http_client.BAD_REQUEST,
                   headers={'X-Auth-Token': token})

    def test_create_application_credential_with_application_credential(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            app_cred_body_1 = self._app_cred_body(roles=roles)
            token = self.get_scoped_token()
            app_cred_1 = c.post('/v3/users/%s/application_credentials' % self.user_id,
                                json=app_cred_body_1,
                                expected_status_code=http_client.CREATED,
                                headers={'X-Auth-Token': token})
            auth_data = self.build_authentication_request(
                app_cred_id=app_cred_1.json['application_credential']['id'],
                secret=app_cred_1.json['application_credential']['secret'])
            token_data = self.v3_create_token(auth_data,
                                              expected_status=http_client.CREATED)
            app_cred_body_2 = self._app_cred_body(roles=roles)
            token = token_data.headers['x-subject-token']
            c.post('/v3/users/%s/application_credentials' % self.user_id,
                   json=app_cred_body_2,
                   expected_status_code=http_client.FORBIDDEN,
                   headers={'X-Auth-Token': token})

    def test_create_application_credential_allow_recursion(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            app_cred_body_1 = self._app_cred_body(roles=roles)
            app_cred_body_1['application_credential']['unrestricted'] = True
            token = self.get_scoped_token()
            app_cred_1 = c.post('/v3/users/%s/application_credentials' % self.user_id,
                                json=app_cred_body_1,
                                expected_status_code=http_client.CREATED,
                                headers={'X-Auth-Token': token})
            auth_data = self.build_authentication_request(
                app_cred_id=app_cred_1.json['application_credential']['id'],
                secret=app_cred_1.json['application_credential']['secret'])
            token_data = self.v3_create_token(auth_data,
                                              expected_status=http_client.CREATED)
            app_cred_body_2 = self._app_cred_body(roles=roles)
            c.post('/v3/users/%s/application_credentials' % self.user_id,
                   json=app_cred_body_2,
                   expected_status_code=http_client.CREATED,
                   headers={'x-Auth-Token': token_data.headers['x-subject-token']})

    def test_list_application_credentials(self):
        with self.test_client() as c:
            token = self.get_scoped_token()
            resp = c.get('/v3/users/%s/application_credentials' % self.user_id,
                         expected_status_code=http_client.OK,
                         headers={'X-Auth-Token': token})
            self.assertEqual([], resp.json['application_credentials'])
            roles = [{'id': self.role_id}]
            app_cred_body = self._app_cred_body(roles=roles)
            c.post('/v3/users/%s/application_credentials' % self.user_id,
                   json=app_cred_body,
                   expected_status_code=http_client.CREATED,
                   headers={'X-Auth-Token': token})
            resp = c.get('/v3/users/%s/application_credentials' % self.user_id,
                         expected_status_code=http_client.OK,
                         headers={'X-Auth-Token': token})
            self.assertEqual(1, len(resp.json['application_credentials']))
            self.assertNotIn('secret', resp.json['application_credentials'][0])
            self.assertNotIn('secret_hash',
                             resp.json['application_credentials'][0])
            app_cred_body['application_credential']['name'] = 'two'
            c.post('/v3/users/%s/application_credentials' % self.user_id,
                   json=app_cred_body,
                   expected_status_code=http_client.CREATED,
                   headers={'X-Auth-Token': token})
            resp = c.get('/v3/users/%s/application_credentials' % self.user_id,
                         expected_status_code=http_client.OK,
                         headers={'X-Auth-Token': token})
            self.assertEqual(2, len(resp.json['application_credentials']))
            for ac in resp.json['application_credentials']:
                self.assertNotIn('secret', ac)
                self.assertNotIn('secret_hash', ac)

    def test_list_application_credentials_by_name(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            app_cred_body = self._app_cred_body(roles=roles)
            token = self.get_scoped_token()
            name = app_cred_body['application_credential']['name']
            search_path = ('/v3/users/%(user_id)s/application_credentials?'
                           'name=%(name)s') % {'user_id': self.user_id,
                                               'name': name}
            resp = c.get(search_path,
                         expected_status_code=http_client.OK,
                         headers={'X-Auth-Token': token})
            self.assertEqual([], resp.json['application_credentials'])
            resp = c.post('/v3/users/%s/application_credentials' % self.user_id,
                          json=app_cred_body,
                          expected_status_code=http_client.CREATED,
                          headers={'X-Auth-Token': token})
            resp = c.get(search_path, expected_status_code=http_client.OK,
                         headers={'X-Auth-Token': token})
            self.assertEqual(1, len(resp.json['application_credentials']))
            self.assertNotIn('secret', resp.json['application_credentials'][0])
            self.assertNotIn('secret_hash',
                             resp.json['application_credentials'][0])
            app_cred_body['application_credential']['name'] = 'two'
            c.post('/v3/users/%s/application_credentials' % self.user_id,
                   json=app_cred_body,
                   expected_status_code=http_client.CREATED,
                   headers={'X-Auth-Token': token})
            resp = c.get(search_path, expected_status_code=http_client.OK,
                         headers={'X-Auth-Token': token})
            self.assertEqual(1, len(resp.json['application_credentials']))
            self.assertEqual(resp.json['application_credentials'][0]['name'], name)

    def test_get_head_application_credential(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            app_cred_body = self._app_cred_body(roles=roles)
            token = self.get_scoped_token()
            resp = c.post('/v3/users/%s/application_credentials' % self.user_id,
                          json=app_cred_body,
                          expected_status_code=http_client.CREATED,
                          headers={'X-Auth-Token': token})
            app_cred_id = resp.json['application_credential']['id']
            c.head('/v3%s' % MEMBER_PATH_FMT % {'user_id': self.user_id,
                                                'app_cred_id': app_cred_id},
                   expected_status_code=http_client.OK,
                   headers={'X-Auth-Token': token})
            expected_response = resp.json
            expected_response['application_credential'].pop('secret')
            resp = c.get('/v3%s' % MEMBER_PATH_FMT % {'user_id': self.user_id,
                         'app_cred_id': app_cred_id},
                         expected_status_code=http_client.OK,
                         headers={'X-Auth-Token': token})
            self.assertDictEqual(resp.json, expected_response)

    def test_get_head_application_credential_not_found(self):
        with self.test_client() as c:
            token = self.get_scoped_token()
            c.head('/v3%s' % MEMBER_PATH_FMT % {'user_id': self.user_id,
                   'app_cred_id': uuid.uuid4().hex},
                   expected_status_code=http_client.NOT_FOUND,
                   headers={'X-Auth-Token': token})
            c.get('/v3%s' % MEMBER_PATH_FMT % {'user_id': self.user_id,
                  'app_cred_id': uuid.uuid4().hex},
                  expected_status_code=http_client.NOT_FOUND,
                  headers={'X-Auth-Token': token})

    def test_delete_application_credential(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            app_cred_body = self._app_cred_body(roles=roles)
            token = self.get_scoped_token()
            resp = c.post('/v3/users/%s/application_credentials' % self.user_id,
                          json=app_cred_body,
                          expected_status_code=http_client.CREATED,
                          headers={'X-Auth-Token': token})
            app_cred_id = resp.json['application_credential']['id']
            c.delete('/v3%s' % MEMBER_PATH_FMT % {'user_id': self.user_id,
                     'app_cred_id': app_cred_id},
                     expected_status_code=http_client.NO_CONTENT,
                     headers={'X-Auth-Token': token})

    def test_delete_application_credential_not_found(self):
        with self.test_client() as c:
            token = self.get_scoped_token()
            c.delete('/v3%s' % MEMBER_PATH_FMT % {'user_id': self.user_id,
                     'app_cred_id': uuid.uuid4().hex},
                     expected_status_code=http_client.NOT_FOUND,
                     headers={'X-Auth-Token': token})

    def test_delete_application_credential_with_application_credential(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            app_cred_body = self._app_cred_body(roles=roles)
            token = self.get_scoped_token()
            app_cred = c.post('/v3/users/%s/application_credentials' % self.user_id,
                              json=app_cred_body,
                              expected_status_code=http_client.CREATED,
                              headers={'X-Auth-Token': token})
            auth_data = self.build_authentication_request(
                app_cred_id=app_cred.json['application_credential']['id'],
                secret=app_cred.json['application_credential']['secret'])
            token_data = self.v3_create_token(auth_data,
                                              expected_status=http_client.CREATED)
            member_path = '/v3%s' % MEMBER_PATH_FMT % {
                          'user_id': self.user_id,
                          'app_cred_id': app_cred.json['application_credential']['id']}
            token = token_data.headers['x-subject-token']
            c.delete(member_path,
                     json=app_cred_body,
                     expected_status_code=http_client.FORBIDDEN,
                     headers={'X-Auth-Token': token})

    def test_delete_application_credential_allow_recursion(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            app_cred_body = self._app_cred_body(roles=roles)
            app_cred_body['application_credential']['unrestricted'] = True
            token = self.get_scoped_token()
            app_cred = c.post('/v3/users/%s/application_credentials' % self.user_id,
                              json=app_cred_body,
                              expected_status_code=http_client.CREATED,
                              headers={'X-Auth-Token': token})
            auth_data = self.build_authentication_request(
                app_cred_id=app_cred.json['application_credential']['id'],
                secret=app_cred.json['application_credential']['secret'])
            token_data = self.v3_create_token(auth_data,
                                              expected_status=http_client.CREATED)
            member_path = '/v3%s' % MEMBER_PATH_FMT % {
                          'user_id': self.user_id,
                          'app_cred_id': app_cred.json['application_credential']['id']}
            c.delete(member_path,
                     json=app_cred_body,
                     expected_status_code=http_client.NO_CONTENT,
                     headers={'x-Auth-Token': token_data.headers['x-subject-token']})

    def test_update_application_credential(self):
        with self.test_client() as c:
            roles = [{'id': self.role_id}]
            app_cred_body = self._app_cred_body(roles=roles)
            token = self.get_scoped_token()
            resp = c.post(
                '/v3/users/%s/application_credentials' % self.user_id,
                json=app_cred_body,
                expected_status_code=http_client.CREATED,
                headers={'X-Auth-Token': token})
            # Application credentials are immutable
            app_cred_body['application_credential'][
                'description'] = "New Things"
            app_cred_id = resp.json['application_credential']['id']
            # NOTE(morgan): when the whole test case is converted to using
            # flask test_client, this extra v3 prefix will
            # need to be rolled into the base MEMBER_PATH_FMT
            member_path = '/v3%s' % MEMBER_PATH_FMT % {
                'user_id': self.user_id,
                'app_cred_id': app_cred_id}
            c.patch(member_path,
                    json=app_cred_body,
                    expected_status_code=http_client.METHOD_NOT_ALLOWED,
                    headers={'X-Auth-Token': token})
