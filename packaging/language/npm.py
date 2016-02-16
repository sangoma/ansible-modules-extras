#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2013, Chris Hoffman <christopher.hoffman@gmail.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: npm
short_description: Manage node.js packages with npm
description:
  - Manage node.js packages with Node Package Manager (npm)
version_added: 1.2
author: Chris Hoffman
options:
  name:
    description:
      - The name of a node.js library to install
    required: false
  path:
    description:
      - The base path where to install the node.js libraries
    required: false
  version:
    description:
      - The version to be installed
    required: false
  global:
    description:
      - Install the node.js library globally
    required: false
    default: no
    choices: [ "yes", "no" ]
  executable:
    description:
      - The executable location for npm.
      - This is useful if you are using a version manager, such as nvm
    required: false
  ignore_scripts:
    description:
      - Use the --ignore-scripts flag when installing.
    required: false
    choices: [ "yes", "no" ]
    default: no
    version_added: "1.8"
  production:
    description:
      - Install dependencies in production mode, excluding devDependencies
    required: false
    choices: [ "yes", "no" ]
    default: no
  registry:
    description:
      - The registry to install modules from.
    required: false
    version_added: "1.6"
  state:
    description:
      - The state of the node.js library
    required: false
    default: present
    choices: [ "present", "absent", "latest" ]
'''

EXAMPLES = '''
description: Install "coffee-script" node.js package.
- npm: name=coffee-script path=/app/location

description: Install "coffee-script" node.js package on version 1.6.1.
- npm: name=coffee-script version=1.6.1 path=/app/location

description: Install "coffee-script" node.js package globally.
- npm: name=coffee-script global=yes

description: Remove the globally package "coffee-script".
- npm: name=coffee-script global=yes state=absent

description: Install "coffee-script" node.js package from custom registry.
- npm: name=coffee-script registry=http://registry.mysite.com

description: Install packages based on package.json.
- npm: path=/app/location

description: Update packages based on package.json to their latest version.
- npm: path=/app/location state=latest

description: Install packages based on package.json using the npm installed with nvm v0.10.1.
- npm: path=/app/location executable=/opt/nvm/v0.10.1/bin/npm state=present
'''

TESTING = '''
# Standalone global with a specific package
        present, specific version should be installed
                "name=browserify global=true version=12.0.1 state=present"

        run again, state should be unmodified
                "name=browserify global=true version=12.0.1 state=present"

        present with new version, already installed package should be upgraded
                "name=browserify global=true version=12.0.2 state=present"

        latest, package should be upgraded to latest
                "name=browserify global=true state=latest"

        absent, package should be removed
                "name=browserify global=true state=absent"

        latest, from the start latest version should be installed
                "name=browserify global=true state=latest"

        run again, state should be unmodified
                "name=browserify global=true state=latest"

        run with same version as latest, should report no changes
                "name=browserify global=true version=13.0.0 state=present"

        try to run absent with a version, should report an error
                "name=browserify global=true version=13.0.0 state=absent"

        try to run latest with a version, should report an error
                "name=browserify global=true version=13.0.0 state=latest"

        absent (again for cleanup), package should be removed
                "name=browserify global=true state=absent"

        present, no specific version, latest should be installed
                "name=browserify global=true state=present"

        run again, state should be unmodified
                "name=browserify global=true state=present"

        absent (again for cleanup), package should be removed
                "name=browserify global=true state=absent"

        absent, state should be unmodified
                "name=browserify global=true state=absent"

# Standalone in directory
        same tests as in global, but path=some-dir/ instead of global=true, packages should be installed locally

# Project with package.json
        same tests as in global, but path=project/ instead of global=true, packages should be installed locally

	Additionally, see issue #957 for testing that modifying the json spec with new packages installs the new packages
'''

import os
try:
    import json
except ImportError:
    import simplejson as json


class Npm(object):
    def __init__(self, module, **kwargs):
        self.module = module
        self.glbl = kwargs['glbl']
        self.name = kwargs['name']
        self.version = kwargs['version']
        self.path = kwargs['path']
        self.registry = kwargs['registry']
        self.production = kwargs['production']
        self.ignore_scripts = kwargs['ignore_scripts']

        if kwargs['executable']:
            self.executable = kwargs['executable'].split(' ')
        else:
            self.executable = [module.get_bin_path('npm', True)]

        if kwargs['version']:
            self.name_version = self.name + '@' + self.version
            self.reqversion = kwargs['version']
        else:
            self.name_version = self.name
            self.reqversion = None

    def _exec(self, args, run_in_check_mode=False, check_rc=True):
        if not self.module.check_mode or (self.module.check_mode and run_in_check_mode):
            cmd = self.executable + args
            if self.glbl:
                cmd.append('--global')
            if self.production:
                cmd.append('--production')
            if self.ignore_scripts:
                cmd.append('--ignore-scripts')
            if self.name:
                cmd.append(self.name_version)
            if self.registry:
                cmd.append('--registry')
                cmd.append(self.registry)

            #If path is specified, cd into that path and run the command.
            cwd = None
            if self.path:
                self.path = os.path.abspath(os.path.expanduser(self.path))
                if not os.path.exists(self.path):
                    os.makedirs(self.path)
                if not os.path.isdir(self.path):
                    self.module.fail_json(msg="path %s is not a directory" % self.path)
                cwd = self.path

            rc, out, err = self.module.run_command(cmd, check_rc=check_rc, cwd=cwd)
            return out
        return ''

    def list(self):
        """Gather a list of installed and missing
        node modules. Try first to use 'npm list' and then
        fallback to 'npm outdated' because 'list' does not
        list devDependencies (not even with a --dev) when the
        project consists of a single package.json and nothing
        has been installed at all yet (that seems like a bug),
        but npm outdated does list them ...
        """
        installed = set()
        missing = set()

        # Use list first
        cmd = ['list', '--json']
        data = json.loads(self._exec(cmd, True, False))
        if 'dependencies' in data:
            for dep in data['dependencies']:
                depinfo = data['dependencies'][dep]
                if ('missing' in depinfo
                   and depinfo['missing']):
                    missing.add(dep)
                elif ('invalid' in depinfo
                      and depinfo['invalid']):
                    missing.add(dep)
                elif (self.reqversion
                      and 'version' in depinfo
                      and depinfo['version'] != self.reqversion):
                    missing.add(dep)
                else:
                    installed.add(dep)

        # Now try using 'outdated' because list does not seem to list missing
        # dev dependencies at all (npm version 3.7.2) even if --dev is
        # specified (though should not be needed unless you only want
        # dev dependencies listed). If this bug is ever fixed on npm, this
        # can be removed.
        try:
            cmd = ['outdated', '--json']
            data = json.loads(self._exec(cmd, True, False))
            installed.update([pkg for pkg, info in data.items()
                              if pkg not in missing
                              and 'location' in info
                              and info['location']])
            missing.update([pkg for pkg, info
                            in data.items()
                            if pkg not in installed
                            and 'current' not in info])
        except ValueError:
            pass

        if self.name and self.name not in installed:
            missing.add(self.name)

        return installed, missing

    def install(self):
        return self._exec(['install'])

    def update(self):
        return self._exec(['update'])

    def uninstall(self):
        return self._exec(['uninstall'])

    def list_outdated(self):
        """Try to get a reliable list of outdated modules.
        It seems older npm versions didn't have the --json
        option for the outdated command. Original code in
        this function was using a regex, so we try to get
        the list with --json first and if it fails fallback
        to the old method of using a regular expression on
        the output. Note that method doesn't support at all
        checking the wanted version so any module that is
        spit out in stdout will be added regardless of whether
        the module is actually up to the latest specified
        version in package.json"""
        outdated = set()
        cmd = ['outdated', '--json']

        def _pkg_is_outdated(pkg, info):
            if 'current' not in info:
                return False
            if self.reqversion:
                # If installed version is different
                # than required version, needs an update
                if info['current'] != self.reqversion:
                    return True
                else:
                    return False
            if info['current'] != info['wanted']:
                return True
            return False

        try:
            data = json.loads(self._exec(cmd, True, False))
            outdated = set([pkg for pkg, info
                            in data.items()
                            if _pkg_is_outdated(pkg, info)])
        except ValueError:
            data = self._exec(cmd[0:1], True, False)
            for dep in data.splitlines():
                if dep:
                    # node.js v0.10.22 changed the `npm outdated` module
                    # separator from "@" to " ". Split on both for
                    # backwards compatibility.
                    pkg, other = re.split('\s|@', dep, 1)
                    # Try to detect and skip if a header is present
                    if (pkg.lower() == 'package'
                       and 'current' in other.lower()):
                        continue
                    outdated.add(pkg)
        return outdated


def main():
    arg_spec = dict(
        name=dict(default=None),
        path=dict(default=None),
        version=dict(default=None),
        production=dict(default='no', type='bool'),
        executable=dict(default=None),
        registry=dict(default=None),
        state=dict(default='present', choices=['present', 'absent', 'latest']),
        ignore_scripts=dict(default=False, type='bool'),
    )
    arg_spec['global'] = dict(default='no', type='bool')
    module = AnsibleModule(
        argument_spec=arg_spec,
        supports_check_mode=True
    )

    name = module.params['name']
    path = module.params['path']
    version = module.params['version']
    glbl = module.params['global']
    production = module.params['production']
    executable = module.params['executable']
    registry = module.params['registry']
    state = module.params['state']
    ignore_scripts = module.params['ignore_scripts']

    if not path and not glbl:
        module.fail_json(msg='path must be specified when not using global')
    if state == 'absent' and not name:
        module.fail_json(msg='uninstalling a package is only available for named packages')
    if state == 'latest' and version:
        module.fail_json(msg='when requesting latest you cannot request a specific version')
    if state == 'absent' and version:
        module.fail_json(msg='when uninstalling packages you cannot request a specific version')

    npm = Npm(module, name=name, path=path, version=version, glbl=glbl, production=production, \
              executable=executable, registry=registry, ignore_scripts=ignore_scripts)

    changed = False
    installed, missing = npm.list()
    if state == 'present':
        # If there are missing modules
        # or no modules at all, attempt
        # an install ...
        if len(missing) or not len(installed):
            changed = True
            npm.install()
    elif state == 'latest':
        outdated = npm.list_outdated()

        # 'npm update <package>' does not do anything
        # if <package> is not installed in the first place
        # so if nothing is installed or the specific
        # package name specified is not installed
        # perform an install rather than an update
        if (not len(installed)
            or (name
                and name not in installed)):
            changed = True
            npm.install()
        elif len(missing) or len(outdated):
            changed = True
            npm.update()
    else:
        # absent ...
        if name in installed:
            changed = True
            npm.uninstall()

    module.exit_json(changed=changed)

# import module snippets
from ansible.module_utils.basic import *
main()
