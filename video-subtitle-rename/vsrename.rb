#!/usr/bin/env ruby
require 'optparse'

options = {}
options[:use_vname] = false
options[:use_sname] = false

optparser = OptionParser.new do |opts|
    opts.banner = "Usage: vsrename.rb [options] vname-pattern sname-pattern [output-pattern]"

    opts.separator("\nOptions:")

    opts.on("-v", "Use the video file name as output file name") do
        options[:use_vname] = true
    end

    opts.on("-s", "Use the subtitle file name as output file name") do
        options[:use_sname] = true
    end
end
optparser.parse!

if ARGV.length < 2 or ARGV.length > 3
    puts optparser.help
    exit(255)
end
