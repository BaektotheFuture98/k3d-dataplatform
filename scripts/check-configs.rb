#!/usr/bin/env ruby
# Offline syntax and repository policy checks. No Kubernetes/API calls.
require 'yaml'

errors = []
documents = 0
empty_files = []

def visit(value, &block)
  case value
  when Hash
    yield value
    value.each_value { |item| visit(item, &block) }
  when Array
    value.each { |item| visit(item, &block) }
  end
end

Dir['deploy/k8s/**/*.yaml'].sort.each do |path|
  content = File.read(path)
  if content.strip.empty?
    empty_files << path
    next
  end
  begin
    YAML.load_stream(content).each do |doc|
      next if doc.nil?
      documents += 1
      next unless path.start_with?('deploy/k8s/manifests/') && doc.is_a?(Hash) && doc['kind']
      errors << "#{path}: namespace must be finance-platform" unless doc.dig('metadata', 'namespace') == 'finance-platform'
      labels = doc.dig('metadata', 'labels') || {}
      %w[name component part-of managed-by].each do |key|
        errors << "#{path}: missing app.kubernetes.io/#{key}" unless labels["app.kubernetes.io/#{key}"]
      end
      if path.start_with?('deploy/k8s/manifests/pipelines/')
        if doc['kind'] == 'Deployment' && doc.dig('spec', 'replicas') != 0
          errors << "#{path}: pipeline Deployment must remain at replicas=0"
        elsif doc['kind'] == 'CronJob' && doc.dig('spec', 'suspend') != true
          errors << "#{path}: pipeline CronJob must remain suspended"
        end
      end
      visit(doc) do |node|
        (node['env'].is_a?(Array) ? node['env'] : []).each do |env|
          name = env['name'].to_s
          next if name.end_with?('_FILE')
          if name.match?(/(?:^|_)(?:PASSWORD|TOKEN|SECRET|ACCESS_KEY_ID)(?:_|$)/) && env['value'] && !env['value'].empty?
            errors << "#{path}: sensitive env #{name} must use a Secret reference"
          end
        end
        (node['containers'].is_a?(Array) ? node['containers'] : []).each do |container|
          %w[requests limits].each do |bound|
            %w[cpu memory].each do |resource|
              errors << "#{path}: #{container['name']} missing #{bound}.#{resource}" unless container.dig('resources', bound, resource)
            end
          end
        end
      end
    end
  rescue StandardError => e
    errors << "#{path}: #{e.class}: #{e.message}"
  end
end

unless errors.empty?
  warn errors.join("\n")
  exit 1
end
puts "Parsed #{documents} YAML documents; namespace, labels, Secret env and suspended pipeline checks passed."
puts "Skipped #{empty_files.length} empty scaffold files (not implemented)."
puts 'Helm values schemas, CRDs, image builds and runtime connections are NOT validated by this check.'
