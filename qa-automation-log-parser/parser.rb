#!/usr/bin/env ruby
require 'fileutils'

TEST_RESULT_ITEMS = [:fail, :succeed, :count, :time, :error, :skipped]

def entry_type(path)
  # detect dir
  if File.directory?(path)
    return :dir
  end
  # detect tarball
  basename = File.basename(path)
  ['tar', 'gz', 'bz2', 'xz'].each do |extname|
    if basename.end_with?(extname)
      return :tarball
    end
  end
  return nil
end

def get_testsuite_name(dir)
  dir = File.basename(dir)
  dir =~ /([\w_\-]+)(?:-\d+){6}/
  if $~
    return $~[1]
  end
  return nil
end

def extract_tarball(tarball)
  tarball = File.expand_path(tarball)
  Dir.chdir('/tmp') do
    # create temporary dir
    time = Time.now.strftime("%m-%d_%H:%M:%S")
    dir = File.basename(tarball).split('.')[0]
    FileUtils.rm_rf(dir)
    FileUtils.mkdir_p(dir)
    # extract the tarball
    Dir.chdir(dir) do
      output = `tar xf '#{tarball}'`
      if $?.exitstatus != 0
        raise StandardError.new("Extraction failed: #{tarball}")
      end
      return Dir.getwd
    end
  end
end

# fail succeed count time error skipped
def parse_test_results(path)
  # read test_results file
  f = File.new(path)
  content = f.read
  f.close

  test_results = {}
  curr_test = nil
  line_num = 0
  content.each_line do |line|
    line_num += 1
    line = line.strip
    if line.length == 0
      next
    elsif line =~ /(\d+\s+){5}\d+/
      digits = line.split(' ')
      if curr_test.nil?
        raise ValueError.new("#{path}:#{line_num} Invalid test_results file")
      end
      test_results[curr_test] = {:dir => File.dirname(path)}
      TEST_RESULT_ITEMS.each_index do |i|
        item = TEST_RESULT_ITEMS[i]
        test_results[curr_test][item] = digits[i].to_i
      end
      curr_test = nil
    else
      unless curr_test.nil?
        raise ValueError.new("#{path}:#{line_num} testcase '#{curr_test}' has no results")
      end
      curr_test = line
    end
  end
  return test_results
end

def select_failed_tests(test_results)
  failed_tests = test_results.select do |test, result|
    if result[:succeed] != result[:count] or
        result[:fail]     != 0 or
        result[:error]    != 0 or
        result[:skipped]  != 0
      true
    else
      false
    end
  end
  # Remove empty testsuites
  return failed_tests
end

def get_status_from_result(result)
  if result[:fail] != 0
    status = 'FAIL'
  elsif result[:error] != 0
    status = 'ERROR'
  elsif result[:skipped] != 0
    status = 'SKIPPED'
  elsif result[:succeed] == result[:count]
    status = 'PASS'
  else
    status = 'ERROR'
  end
  return status
end

def print_test_results(test_results)
  # print title
  title = "Test".ljust(35) + "Status".ljust(10) + "Time".ljust(7) + "Log"
  puts title
  # print test results
  test_results.each_pair do |test, result|
    status = get_status_from_result(result)
    time = result[:time]
    line = test.ljust(35) + status.ljust(10) + time.to_s.ljust(7)
    line << File.join(File.basename(result[:dir]), test)
    puts line
  end
end

def usage
  info = <<END
Usage: #{$0} ENTRY1 [ENTRY2 ENTRY3 ...]

Each ENTRY can be a directory or tarball.
If it's a tarball, extract it to a temporary directory before analyzing.
END
  puts info
end

if __FILE__ == $0
  if ARGV.length == 0
    usage
    exit 255
  end

  test_results_files = {}
  ARGV.each do |entry|
    entry = File.expand_path(entry)
    type = entry_type(entry)
    if type == :tarball
      dir = extract_tarball(entry)
      Dir.foreach(dir) do |name|
        if File.directory?(File.join(dir, name)) and (not ['.', '..'].include?(name))
          key = get_testsuite_name(name)
          value = File.join(dir, name, 'test_results')
          test_results_files[key] = value
        end
      end
    elsif type == :dir
      key = get_testsuite_name(File.basename(entry))
      test_results_files[key] = File.join(entry, 'test_results')
    end
  end

  # print report
  if test_results_files.empty?
    STDERR.write("Fatal Error: No test_results files found!\n")
    exit 1
  end
  test_results_files.each_pair do |testsuite, results_file|
    if not File.exist?(results_file)
        STDERR.write("test_results file missing: #{results_file}\n")
        next
    end
    results = parse_test_results(results_file)
    failed_tests = select_failed_tests(results)
    unless failed_tests.empty?
      puts ">> Testsuite: #{testsuite} ".ljust(80, "=")
      print_test_results(failed_tests)
      puts ""
    end
  end
end
