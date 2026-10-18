#!/usr/bin/env ruby
# Run from project root; source configuration stays in configs/garage/.
require 'yaml'

{
  'garage-config' => ['garage.toml', 'configs/garage/garage.toml', 'configmap.yaml'],
  'garage-s3-check' => ['s3-check.py', 'configs/garage/s3-check.py', 'check-configmap.yaml']
}.each do |name, (key, source, target)|
  resource = {
    'apiVersion' => 'v1', 'kind' => 'ConfigMap',
    'metadata' => {
      'name' => name, 'namespace' => 'finance-platform',
      'labels' => {
        'app.kubernetes.io/name' => 'garage',
        'app.kubernetes.io/component' => 'object-storage',
        'app.kubernetes.io/part-of' => 'finance-platform',
        'app.kubernetes.io/managed-by' => 'kubectl'
      }
    },
    'data' => {key => File.read(source)}
  }
  File.write("deploy/k8s/manifests/garage/#{target}", YAML.dump(resource))
end
